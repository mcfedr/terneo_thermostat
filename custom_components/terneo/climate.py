"""Climate platform for Terneo thermostats."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_PRIMARY_SENSOR,
    DOMAIN,
    MAX_TEMP,
    MIN_TEMP,
    PRESET_AWAY,
    PRESET_MANUAL,
    PRESET_SCHEDULE,
    PRIMARY_AIR,
    PRIMARY_FLOOR,
    TEMP_STEP,
)
from .coordinator import TerneoCoordinator
from .entity import TerneoEntity

_LOGGER = logging.getLogger(__name__)

SUPPORTED_HVAC_MODES = [HVACMode.OFF, HVACMode.AUTO, HVACMode.HEAT]
SUPPORTED_PRESETS = [PRESET_SCHEDULE, PRESET_MANUAL, PRESET_AWAY]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Terneo climate entity."""
    coordinator: TerneoCoordinator = hass.data[DOMAIN][entry.entry_id]
    primary = entry.options.get(
        CONF_PRIMARY_SENSOR, entry.data.get(CONF_PRIMARY_SENSOR, PRIMARY_AIR)
    )
    async_add_entities([TerneoClimate(coordinator, primary)])


class TerneoClimate(TerneoEntity, ClimateEntity):
    """Main thermostat entity for a Terneo device."""

    _attr_name = None  # Use the device name
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = SUPPORTED_HVAC_MODES
    _attr_preset_modes = SUPPORTED_PRESETS
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_target_temperature_step = TEMP_STEP
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: TerneoCoordinator, primary_sensor: str) -> None:
        super().__init__(coordinator)
        self._primary_sensor = primary_sensor
        self._attr_unique_id = f"{coordinator.client.serial}_climate"

    # --------------------------------------------------------------- readings

    @property
    def current_temperature(self) -> float | None:
        data = self.coordinator.data
        if data is None:
            return None
        if self._primary_sensor == PRIMARY_FLOOR:
            return data.floor_temp if data.floor_temp is not None else data.air_temp
        return data.air_temp if data.air_temp is not None else data.floor_temp

    @property
    def target_temperature(self) -> float | None:
        return self.coordinator.data.setpoint if self.coordinator.data else None

    @property
    def hvac_mode(self) -> HVACMode:
        data = self.coordinator.data
        if data is None or not data.is_on:
            return HVACMode.OFF
        if data.is_schedule:
            return HVACMode.AUTO
        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        data = self.coordinator.data
        if data is None or not data.is_on:
            return HVACAction.OFF
        return HVACAction.HEATING if data.is_heating else HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        data = self.coordinator.data
        if data is None or not data.is_on:
            return None
        if data.is_away:
            return PRESET_AWAY
        if data.is_schedule:
            return PRESET_SCHEDULE
        return PRESET_MANUAL

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        if data is None:
            return {}
        return {
            "floor_temperature": data.floor_temp,
            "air_temperature": data.air_temp,
            "raw_mode": data.mode,
        }

    # --------------------------------------------------------------- commands

    async def async_turn_on(self) -> None:
        await self.coordinator.async_write(
            lambda: self.coordinator.client.async_set_power(on=True)
        )

    async def async_turn_off(self) -> None:
        await self.coordinator.async_write(
            lambda: self.coordinator.client.async_set_power(on=False)
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        client = self.coordinator.client
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_write(lambda: client.async_set_power(on=False))
        elif hvac_mode == HVACMode.AUTO:
            await self.coordinator.async_write(
                lambda: client.async_set_mode(schedule=True)
            )
        elif hvac_mode == HVACMode.HEAT:
            await self.coordinator.async_write(
                lambda: client.async_set_mode(schedule=False)
            )
        else:
            _LOGGER.warning("Unsupported HVAC mode requested: %s", hvac_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        client = self.coordinator.client
        if preset_mode == PRESET_SCHEDULE:
            await self.coordinator.async_write(
                lambda: client.async_set_mode(schedule=True)
            )
        elif preset_mode == PRESET_MANUAL:
            await self.coordinator.async_write(
                lambda: client.async_set_mode(schedule=False)
            )
        elif preset_mode == PRESET_AWAY:
            # Device doesn't accept mode=4 directly via par 2; the closest
            # local-API substitute is manual mode with an away setpoint.
            # We leave the setpoint alone and just flip into manual; users
            # who need true scheduled away should use the Terneo app.
            _LOGGER.info(
                "Terneo 'away' preset is not settable via the local API; "
                "falling back to manual mode"
            )
            await self.coordinator.async_write(
                lambda: client.async_set_mode(schedule=False)
            )
        else:
            _LOGGER.warning("Unknown preset requested: %s", preset_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        temp_int = int(round(float(temperature)))
        await self.coordinator.async_write(
            lambda: self.coordinator.client.async_set_setpoint(temp_int)
        )
