"""Async client for the Terneo local HTTP API.

Implements the minimum of https://terneo-api.readthedocs.io/ that this
integration needs:

* POST http://{host}:{port}/api.cgi  with a JSON body
* ``{"cmd": 4, "sn": "<serial>"}``  -> telemetry (temperatures in 1/16 °C)
* ``{"sn": "<serial>", "par": [[id, type, value], ...]}`` -> write params
  (setpoints in whole °C)

Important behaviors:

* The device serializes requests. If a second command arrives while the
  previous one is still being processed, the device returns
  ``{"status": "timeout"}``. We retry a limited number of times with a short
  backoff rather than marking the device unavailable.
* Responses are always valid JSON on success, but can be empty or HTML on a
  misconfigured / locked device -> treated as connection errors.
* When the LAN lock is enabled (``bLc`` on), write requests must be signed
  with a TOTP token derived from a per-device key fetched from the Terneo
  cloud. Read requests work without authentication regardless of lock state.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import struct
from typing import Any

import aiohttp
from aiohttp import ClientError, ClientResponseError, ClientTimeout

from .const import (
    API_ENDPOINT,
    CMD_TELEMETRY,
    PAR_MODE,
    PAR_POWER,
    PAR_SETPOINT,
    TELEM_TIME,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = ClientTimeout(total=8)
MIN_INTERVAL = 0.5  # seconds between requests (device is sensitive to spam)
BUSY_RETRIES = 3
BUSY_BACKOFF = 0.8


class TerneoError(Exception):
    """Base class for Terneo API errors."""


class TerneoConnectionError(TerneoError):
    """Raised when the device is unreachable."""


class TerneoApiLockedError(TerneoError):
    """Raised when the local API is locked (``bLc`` is on)."""


class TerneoBusyError(TerneoError):
    """Raised when the device keeps returning ``status=timeout``."""


class TerneoClient:
    """Thin async wrapper around the Terneo local HTTP API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        serial: str,
        *,
        port: int = 80,
        totp_key: str | None = None,
    ) -> None:
        self._session = session
        self.host = host
        self.port = port
        self.serial = serial
        self._totp_key = totp_key
        self._url = f"http://{host}:{port}/{API_ENDPOINT}"
        self._lock = asyncio.Lock()
        self._last_request: float = 0.0

    # ------------------------------------------------------------------ utils

    async def _throttle(self) -> None:
        """Make sure successive requests are spaced out a little."""
        loop = asyncio.get_running_loop()
        now = loop.time()
        wait = MIN_INTERVAL - (now - self._last_request)
        if wait > 0:
            await asyncio.sleep(wait)

    async def _raw_post(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a JSON payload. Caller must hold ``self._lock``."""
        await self._throttle()

        last_exc: Exception | None = None
        for attempt in range(BUSY_RETRIES):
            try:
                async with self._session.post(
                    self._url,
                    json=payload,
                    timeout=REQUEST_TIMEOUT,
                ) as resp:
                    self._last_request = asyncio.get_running_loop().time()
                    if resp.status != 200:
                        raise TerneoConnectionError(
                            f"Unexpected HTTP {resp.status} from {self._url}"
                        )
                    try:
                        data = await resp.json(content_type=None)
                    except (aiohttp.ContentTypeError, ValueError) as err:
                        raise TerneoApiLockedError(
                            "Device returned non-JSON response. "
                            "The local API is probably locked — "
                            "set bLc to off on the device."
                        ) from err
            except (asyncio.TimeoutError, ClientError, ClientResponseError) as err:
                last_exc = err
                # Real network error: retry once, then give up
                if attempt == BUSY_RETRIES - 1:
                    raise TerneoConnectionError(str(err)) from err
                await asyncio.sleep(BUSY_BACKOFF)
                continue

            if isinstance(data, dict) and data.get("status") == "timeout":
                # Device busy — brief backoff and retry
                _LOGGER.debug(
                    "Terneo %s busy (status=timeout), attempt %s/%s",
                    self.serial,
                    attempt + 1,
                    BUSY_RETRIES,
                )
                await asyncio.sleep(BUSY_BACKOFF * (attempt + 1))
                continue

            if not isinstance(data, dict):
                raise TerneoConnectionError(f"Unexpected response: {data!r}")

            return data

        raise TerneoBusyError(
            f"Device {self.serial} remained busy after {BUSY_RETRIES} retries"
        ) from last_exc

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a JSON payload, serialized with the request lock."""
        async with self._lock:
            return await self._raw_post(payload)

    # ------------------------------------------------------------------- totp

    def _compute_totp(self, device_time: int) -> str:
        """Compute a 9-digit TOTP token for the given device time.

        The Terneo device uses HMAC-SHA1 (RFC 4226/6238) with a 30-second
        interval and 9-digit codes. The key is the raw UTF-8 bytes of the
        ``totp_key`` string from the cloud API — *not* base32-decoded.
        The counter is ``device_time // 30`` where ``device_time`` is seconds
        since 2000-01-01 UTC (the ``time`` field in telemetry).
        """
        assert self._totp_key is not None
        key = self._totp_key.encode("utf-8")
        counter = device_time // 30
        msg = struct.pack(">Q", counter)
        h = hmac.new(key, msg, hashlib.sha1).digest()
        offset = h[-1] & 0x0F
        code = struct.unpack(">I", h[offset : offset + 4])[0] & 0x7FFFFFFF
        return str(code % (10**9)).zfill(9)

    async def _signed_post(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a write payload signed with TOTP.

        Reads telemetry first to obtain the device's current clock, computes
        the TOTP token, injects ``time`` and ``auth`` into the payload, then
        sends it. Both requests run under a single lock acquisition to avoid
        deadlock and keep the time→write gap tight.

        Falls back to a plain ``_post`` when no TOTP key is configured
        (device has LAN lock off).
        """
        if not self._totp_key:
            return await self._post(payload)

        async with self._lock:
            telem = await self._raw_post({"cmd": CMD_TELEMETRY, "sn": self.serial})
            device_time = int(telem[TELEM_TIME])
            payload["time"] = str(device_time)
            payload["auth"] = self._compute_totp(device_time)
            return await self._raw_post(payload)

    # ---------------------------------------------------------------- reading

    async def async_get_telemetry(self) -> dict[str, Any]:
        """Return live telemetry (cmd=4)."""
        return await self._post({"cmd": CMD_TELEMETRY, "sn": self.serial})

    # ---------------------------------------------------------------- writing

    async def _set_par(self, params: list[list[Any]]) -> None:
        """Write one or more parameters."""
        await self._signed_post({"sn": self.serial, "par": params})

    async def async_set_power(self, *, on: bool) -> None:
        """Turn the device on or off (par 125)."""
        value = "0" if on else "1"  # 0=on, 1=off (yes, really)
        await self._set_par([[PAR_POWER[0], PAR_POWER[1], value]])

    async def async_set_mode(self, *, schedule: bool) -> None:
        """Switch between schedule (AUTO) and manual (HEAT) mode.

        Also forces power on so that setting a mode actually takes effect.
        """
        mode_value = "0" if schedule else "1"
        await self._set_par(
            [
                [PAR_POWER[0], PAR_POWER[1], "0"],  # power on
                [PAR_MODE[0], PAR_MODE[1], mode_value],
            ]
        )

    async def async_set_setpoint(self, temperature: int) -> None:
        """Set manual-mode setpoint (par 5), and ensure device is on + manual."""
        await self._set_par(
            [
                [PAR_POWER[0], PAR_POWER[1], "0"],  # power on
                [PAR_MODE[0], PAR_MODE[1], "1"],  # manual
                [PAR_SETPOINT[0], PAR_SETPOINT[1], str(int(temperature))],
            ]
        )

    # -------------------------------------------------------------- lifecycle

    async def async_probe(self) -> dict[str, Any]:
        """Fetch telemetry once — used by config flow to validate connectivity."""
        return await self.async_get_telemetry()
