"""One-shot helper to fetch a TOTP key from the Terneo cloud.

Used during config flow setup only. The integration does not maintain an
ongoing cloud connection — once the key is stored in the config entry, all
communication is local.

Cloud API: https://my.hmarex.com/api/
"""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

CLOUD_BASE = "https://my.hmarex.com/api"


class TerneoCloudError(Exception):
    """Base for cloud API errors."""


class TerneoCloudAuthError(TerneoCloudError):
    """Login to the Terneo cloud failed."""


class TerneoCloudDeviceNotFoundError(TerneoCloudError):
    """The serial number was not found in the user's cloud account."""


async def async_fetch_totp_key(
    session: aiohttp.ClientSession,
    email: str,
    password: str,
    serial: str,
) -> str:
    """Log in to the Terneo cloud and return the TOTP key for *serial*.

    Raises ``TerneoCloudAuthError`` if the login fails and
    ``TerneoCloudDeviceNotFoundError`` if the serial is not in the account.
    """
    # Step 1: authenticate
    try:
        async with session.post(
            f"{CLOUD_BASE}/login/",
            json={"email": email, "password": password},
        ) as resp:
            if resp.status != 200:
                raise TerneoCloudAuthError(
                    f"Cloud login failed (HTTP {resp.status})"
                )
            login: dict[str, Any] = await resp.json()
    except (aiohttp.ClientError, TimeoutError) as err:
        raise TerneoCloudAuthError(f"Could not reach Terneo cloud: {err}") from err

    token = login.get("access_token")
    if not token:
        raise TerneoCloudAuthError("Cloud login succeeded but no access_token returned")

    # Step 2: fetch device list
    try:
        async with session.get(
            f"{CLOUD_BASE}/device/",
            headers={
                "Authorization": f"Token {token}",
                "Content-Type": "application/json",
            },
        ) as resp:
            if resp.status != 200:
                raise TerneoCloudError(
                    f"Could not fetch devices (HTTP {resp.status})"
                )
            data: dict[str, Any] = await resp.json()
    except (aiohttp.ClientError, TimeoutError) as err:
        raise TerneoCloudError(f"Cloud device list request failed: {err}") from err

    # Step 3: find matching serial
    serial_clean = serial.strip().upper()
    for device in data.get("results", []):
        dev_sn = str(device.get("sn", "")).strip().upper()
        if dev_sn == serial_clean:
            key = device.get("totp_key")
            if not key:
                raise TerneoCloudDeviceNotFoundError(
                    f"Device {serial} found but has no totp_key"
                )
            return str(key)

    raise TerneoCloudDeviceNotFoundError(
        f"Serial {serial} not found in your Terneo cloud account"
    )
