# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Home Assistant custom integration for Terneo AX/SX/RX Wi-Fi thermostats. Communicates locally via the device's HTTP API (`POST /api.cgi`) — no cloud or MQTT. Installed via HACS or manual copy to `custom_components/terneo/`.

## Commands

```bash
# Run tests (no Home Assistant installation needed)
pip install pytest pytest-asyncio pytest-cov
pytest tests/ -v

# Run a single test
pytest tests/test_manifest.py -v

# CI also runs these (require separate tools):
# hacs validate
# hassfest
```

Versioning is automated: pushing to main triggers CI that bumps the patch version in `manifest.json`, commits, tags, and creates a GitHub release.

## Architecture

The integration follows standard Home Assistant patterns with these components:

- **`api.py`** — `TerneoClient`: async HTTP client wrapping the device's local API. Serializes requests with asyncio.Lock, enforces 0.5s minimum interval between requests, retries on device-busy (`status=timeout`) with exponential backoff. Supports optional HTTP Basic Auth.
- **`coordinator.py`** — `TerneoCoordinator(DataUpdateCoordinator)`: polls every 30s, normalizes raw telemetry into a `TerneoData` dataclass. The `async_write(coro_factory)` pattern runs a write then immediately refreshes data. Auth errors trigger HA's reauth flow; connection errors mark entities unavailable.
- **`config_flow.py`** — Manual setup and auto-discovery (via UDP). Immutable data (host/port/serial) stored in `entry.data`; mutable settings (power_watts, primary_sensor) in `entry.options` with an options flow.
- **`climate.py`** — Climate entity. Maps device modes (0=schedule, 3=manual, 4=away) to HA's HVACMode/Preset system.
- **`sensor.py`** — Floor temp (enabled), air temp (disabled by default), optional power sensor (watts while heating, 0 while idle).
- **`entity.py`** — `TerneoEntity(CoordinatorEntity)`: shared base with `has_entity_name=True` and device registry setup.
- **`discovery.py`** — UDP broadcast listener on port 23500. Parses device JSON broadcasts and feeds new serials into the config flow.
- **`__init__.py`** — Starts discovery listener at HA startup, deduplicates via `_seen_serials` set, updates config entry IP if a known serial appears from a new address.

## Key Implementation Details

- **Temperature encoding**: device uses 1/16°C steps — multiply by 16 for writes, divide by 16 for reads.
- **Power state detection** is firmware-dependent: FW 2.4+ reads `f.16` directly; FW 2.3 infers from mode field presence.
- **Write parameters** use `par` array format with `(parameter_id, type)` tuples defined in `const.py`.
- **No external Python dependencies** — uses only HA-bundled libraries (aiohttp, voluptuous).
- **Unique IDs**: `{serial}_climate`, `{serial}_floor_temperature`, `{serial}_air_temperature`, `{serial}_power`.

## Testing

Tests run under plain pytest without Home Assistant installed. They validate JSON config files (manifest, hacs.json, strings/translations structure) and constant invariants (mode uniqueness, parameter shapes, temperature bounds). The test suite intentionally avoids mocking the HA ecosystem.
