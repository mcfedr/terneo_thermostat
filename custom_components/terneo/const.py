"""Constants for the Terneo integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "terneo"
MANUFACTURER: Final = "DS Electronics"
DEFAULT_NAME: Final = "Terneo"
DEFAULT_PORT: Final = 80
DEFAULT_SCAN_INTERVAL: Final = 30  # seconds

# Config entry keys
CONF_SERIAL: Final = "serial"
CONF_POWER_WATTS: Final = "power_watts"
CONF_PRIMARY_SENSOR: Final = "primary_sensor"
CONF_TOTP_KEY: Final = "totp_key"

# Primary sensor selection (which temperature to show on the climate entity)
PRIMARY_AIR: Final = "air"
PRIMARY_FLOOR: Final = "floor"

# Min/max temperature bounds supported by Terneo firmware
MIN_TEMP: Final = 5
MAX_TEMP: Final = 45
TEMP_STEP: Final = 1.0

# --- Terneo local HTTP API ---
# POST http://{host}:{port}/api.cgi
API_ENDPOINT: Final = "api.cgi"

# Commands
CMD_TELEMETRY: Final = 4  # live telemetry (temps, relay state, mode)

# Telemetry keys (values in 1/16°C where applicable)
TELEM_TIME: Final = "time"  # device clock, seconds since 2000-01-01 UTC
TELEM_FLOOR_TEMP: Final = "t.1"  # floor sensor
TELEM_AIR_TEMP: Final = "t.2"  # air sensor
TELEM_SETPOINT: Final = "t.5"  # current setpoint
TELEM_MODE: Final = "m.1"  # 0=schedule, 3=manual, 4=away
TELEM_RELAY: Final = "f.0"  # 1=relay on (heating), 0=off
TELEM_POWER_STATE: Final = "f.16"  # fw 2.4+: 0=on, 1=off

# Mode values reported by device (m.1)
MODE_SCHEDULE: Final = 0
MODE_MANUAL: Final = 3
MODE_AWAY: Final = 4

# Parameter ids for writes (par = [[id, type, value], ...])
PAR_POWER: Final = (125, 7)  # value "0" = on, "1" = off
PAR_MODE: Final = (2, 2)  # value "0"=schedule, "1"=manual
PAR_SETPOINT: Final = (5, 1)  # integer degrees as string

# Preset names
PRESET_SCHEDULE: Final = "schedule"
PRESET_MANUAL: Final = "manual"
PRESET_AWAY: Final = "away"
