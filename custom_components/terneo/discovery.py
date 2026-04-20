"""UDP broadcast discovery for Terneo thermostats.

Terneo Wi-Fi thermostats (firmware 2.3+) emit a JSON broadcast on UDP port
23500 every ~30 seconds:

    {"sn":"058016…","hw":"ax","cloud":"true",
     "connection":"cloudCon","wifi":"-71","display":"23.0"}

See https://terneo-api.readthedocs.io/ru/latest/en/broadcast.html

We listen for those packets from the moment Home Assistant starts, feed
each new ``sn`` into an ``integration_discovery`` config flow, and update
the stored IP of an already-configured device if it changes.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import json
import logging
import socket
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

BROADCAST_PORT = 23500
OnDeviceCallback = Callable[[dict[str, Any], str], Awaitable[None]]


class _TerneoBroadcastProtocol(asyncio.DatagramProtocol):
    """Parses incoming UDP broadcasts and forwards them to a callback."""

    def __init__(self, hass: HomeAssistant, on_device: OnDeviceCallback) -> None:
        self._hass = hass
        self._on_device = on_device

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            payload = json.loads(data.decode("utf-8", errors="replace"))
        except (ValueError, UnicodeDecodeError):
            return
        if not isinstance(payload, dict) or "sn" not in payload:
            return
        # Schedule the async handler on the HA event loop
        self._hass.async_create_task(self._on_device(payload, addr[0]))

    def error_received(self, exc: Exception) -> None:  # pragma: no cover
        _LOGGER.debug("Terneo discovery socket error: %s", exc)


async def async_start_listener(hass: HomeAssistant, on_device: OnDeviceCallback):
    """Start listening for Terneo broadcasts.

    Returns the asyncio transport so the caller can close it on HA shutdown.
    Returns ``None`` and logs a warning if the port is unavailable — the
    integration still works, just without auto-discovery.
    """
    loop = asyncio.get_running_loop()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # SO_REUSEPORT lets us coexist with other apps listening on the same
    # port (e.g. the official Terneo mobile app on the same host, or a
    # second integration instance in a test setup). Not universally
    # supported, so we ignore failures.
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except (AttributeError, OSError):
        pass

    try:
        sock.bind(("0.0.0.0", BROADCAST_PORT))
    except OSError as err:
        sock.close()
        _LOGGER.warning(
            "Could not bind to UDP port %s for Terneo discovery (%s). "
            "Auto-discovery will be disabled; add devices manually instead. "
            "If you run Home Assistant in Docker, ensure host networking is "
            "enabled or that UDP broadcasts reach the container.",
            BROADCAST_PORT,
            err,
        )
        return None
    sock.setblocking(False)

    transport, _ = await loop.create_datagram_endpoint(
        lambda: _TerneoBroadcastProtocol(hass, on_device),
        sock=sock,
    )
    _LOGGER.debug("Terneo UDP discovery listening on port %s", BROADCAST_PORT)
    return transport
