"""DataUpdateCoordinator for the Terneo integration.

One coordinator per device. Polls telemetry at a fixed interval and exposes
a normalized snapshot to the platforms.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TerneoApiLockedError, TerneoClient, TerneoConnectionError, TerneoError
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MODE_AWAY,
    MODE_MANUAL,
    MODE_SCHEDULE,
    TELEM_AIR_TEMP,
    TELEM_FLOOR_TEMP,
    TELEM_MODE,
    TELEM_POWER_STATE,
    TELEM_RELAY,
    TELEM_SETPOINT,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class TerneoData:
    """Normalized snapshot of one device."""

    floor_temp: float | None
    air_temp: float | None
    setpoint: float | None
    mode: int | None  # raw m.1 value, or None if unknown
    is_heating: bool
    is_on: bool
    raw: dict[str, Any]

    @property
    def is_schedule(self) -> bool:
        return self.mode == MODE_SCHEDULE

    @property
    def is_manual(self) -> bool:
        return self.mode == MODE_MANUAL

    @property
    def is_away(self) -> bool:
        return self.mode == MODE_AWAY


def _deg(raw: Any) -> float | None:
    """Decode a temperature value (device reports in 1/16 °C units)."""
    if raw is None:
        return None
    try:
        return round(float(raw) / 16.0, 1)
    except (TypeError, ValueError):
        return None


def _int(raw: Any) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


class TerneoCoordinator(DataUpdateCoordinator[TerneoData]):
    """Polls one Terneo device."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: TerneoClient,
        *,
        name: str,
    ) -> None:
        self.client = client
        self.display_name = name
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {name}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> TerneoData:
        try:
            telem = await self.client.async_get_telemetry()
        except TerneoApiLockedError as err:
            raise UpdateFailed(
                f"Local API is locked on the device — set bLc to off: {err}"
            ) from err
        except TerneoConnectionError as err:
            raise UpdateFailed(f"Connection error: {err}") from err
        except TerneoError as err:
            raise UpdateFailed(str(err)) from err

        power_state = _int(telem.get(TELEM_POWER_STATE))
        relay = _int(telem.get(TELEM_RELAY))
        mode = _int(telem.get(TELEM_MODE))

        # f.16: 0 = on, 1 = off (firmware 2.4+)
        is_on = power_state == 0

        return TerneoData(
            floor_temp=_deg(telem.get(TELEM_FLOOR_TEMP)),
            air_temp=_deg(telem.get(TELEM_AIR_TEMP)),
            setpoint=_deg(telem.get(TELEM_SETPOINT)),
            mode=mode,
            is_heating=relay == 1,
            is_on=is_on,
            raw=telem,
        )

    async def async_write(
        self, coro_factory: Callable[[], Awaitable[Any]]
    ) -> None:
        """Run a write coroutine, then refresh state immediately.

        ``coro_factory`` is a callable returning the awaitable so the caller
        can guarantee ordering (write → read) without holding references to
        a stale coroutine. Uses ``async_refresh`` (not the debounced request
        variant) so the UI reflects the new state the moment the service
        call returns.
        """
        await coro_factory()
        await self.async_refresh()
