"""Base class for Terneo entities."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import TerneoCoordinator


class TerneoEntity(CoordinatorEntity[TerneoCoordinator]):
    """Common setup: device registry info, unique_id prefix, availability."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TerneoCoordinator) -> None:
        super().__init__(coordinator)
        serial = coordinator.client.serial
        host = coordinator.client.host
        port = coordinator.client.port
        config_url = f"http://{host}/" if port == 80 else f"http://{host}:{port}/"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer=MANUFACTURER,
            model="Wi-Fi Thermostat",
            name=coordinator.display_name,
            serial_number=serial,
            configuration_url=config_url,
        )
