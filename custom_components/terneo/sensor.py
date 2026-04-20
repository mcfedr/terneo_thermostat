"""Sensor platform for Terneo thermostats.

Exposes the floor-sensor temperature as a separate entity (the climate entity
already exposes one primary temperature) and, when the user configured the
heater's wattage, a real-time power sensor that's ``watts`` while the relay
is on and ``0`` when it's off. That's enough for Home Assistant's Energy
dashboard to accumulate kWh via a Riemann-sum helper.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_POWER_WATTS, DOMAIN
from .coordinator import TerneoCoordinator, TerneoData
from .entity import TerneoEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class TerneoSensorEntityDescription(SensorEntityDescription):
    """Describes a Terneo sensor."""

    value_fn: Callable[[TerneoData], float | int | None]


FLOOR_TEMP = TerneoSensorEntityDescription(
    key="floor_temperature",
    translation_key="floor_temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    value_fn=lambda d: d.floor_temp,
)

AIR_TEMP = TerneoSensorEntityDescription(
    key="air_temperature",
    translation_key="air_temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    entity_registry_enabled_default=False,
    value_fn=lambda d: d.air_temp,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Terneo sensors."""
    coordinator: TerneoCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        TerneoSensor(coordinator, FLOOR_TEMP),
        TerneoSensor(coordinator, AIR_TEMP),
    ]

    watts = entry.options.get(CONF_POWER_WATTS, entry.data.get(CONF_POWER_WATTS))
    if watts:
        try:
            watts_int = int(watts)
        except (TypeError, ValueError):
            _LOGGER.warning("Invalid %s: %r", CONF_POWER_WATTS, watts)
        else:
            if watts_int > 0:
                entities.append(TerneoPowerSensor(coordinator, watts_int))

    async_add_entities(entities)


class TerneoSensor(TerneoEntity, SensorEntity):
    """Generic value sensor (temperatures)."""

    entity_description: TerneoSensorEntityDescription

    def __init__(
        self,
        coordinator: TerneoCoordinator,
        description: TerneoSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.client.serial}_{description.key}"

    @property
    def native_value(self) -> float | int | None:
        data = self.coordinator.data
        if data is None:
            return None
        return self.entity_description.value_fn(data)


class TerneoPowerSensor(TerneoEntity, SensorEntity):
    """Instantaneous power: configured watts while heating, else 0."""

    _attr_translation_key = "power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator: TerneoCoordinator, watts: int) -> None:
        super().__init__(coordinator)
        self._watts = watts
        self._attr_unique_id = f"{coordinator.client.serial}_power"

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data
        if data is None:
            return None
        if not data.is_on:
            return 0
        return self._watts if data.is_heating else 0
