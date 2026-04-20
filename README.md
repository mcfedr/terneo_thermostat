# Terneo Thermostat — Home Assistant integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

A modern, local-only Home Assistant integration for Terneo Wi-Fi
thermostats (terneo AX / SX / RX and similar, made by DS Electronics,
sold at my.terneo.ua). Talks directly to the device on your LAN using
the official [Terneo local HTTP API](https://terneo-api.readthedocs.io/);
no cloud account and no MQTT broker required.

This is a rewrite of the older `Makave1i/terneo_thermostat` component.

## What's new vs. the original

| | Old | This version |
|---|---|---|
| Setup | YAML in `configuration.yaml` | UI config flow |
| I/O | Synchronous `requests` (blocked HA event loop) | Async `aiohttp` |
| Coordinator | Per-entity polling | Single `DataUpdateCoordinator` per device |
| Busy device (`status=timeout`) | Marked unavailable | Brief retry with backoff |
| `current_temperature` | Floor sensor regardless of setup | Air sensor by default, user-selectable |
| Floor temperature | Not exposed | Dedicated sensor entity |
| Power | Not exposed | Optional watts-aware power sensor for the Energy dashboard |
| Integration files | `climate.py` + `thermostat.py` | Split into `api.py`, `coordinator.py`, `config_flow.py`, `climate.py`, `sensor.py`, `entity.py`, `const.py` |

## Requirements

- Terneo Wi-Fi thermostat with firmware **2.3+**.
- Local API access unlocked on the device. Firmware 2.3+ ships with local
  control blocked by default — see the
  [safety page](https://terneo-api.readthedocs.io/ru/latest/en/safety.html)
  of the API docs for the on-device toggle.
- Device IP address and serial number. The serial is printed on the
  sticker and shown on `http://<device-ip>/index.html`.

## Installation

### HACS (recommended)

1. HACS → ⋮ → **Custom repositories** → add
   `https://github.com/mcfedr/homeassistant-terneo-integration` as an **Integration**.
2. Install **Terneo Thermostat** from HACS.
3. Restart Home Assistant.
4. **Settings → Devices & services → Add integration → Terneo**.

### Manual

Copy `custom_components/terneo/` into your `config/custom_components/`
folder, restart Home Assistant, then add the integration from the UI.

## Configuration

The config flow asks for:

- **Host / IP** — e.g. `192.168.1.50`.
- **Serial number** — 10-digit number from the device sticker.
- **Name** — display name for the entity / device card.
- **Port** — default `80`, usually correct.
- **TOTP key** — optional. Required only when the device's LAN lock
  (`bLc`) is enabled. You can paste the key directly, or leave it blank
  and choose **Fetch from Terneo cloud** on the next screen to pull it
  from your my.terneo.ua account automatically. Cloud credentials are
  used once and never stored.
- **Heater power (W)** — optional. If set, exposes a `sensor.*_power`
  entity that reads the configured wattage when the relay is on and `0`
  when it's off. Drop it into a Riemann-sum or utility-meter helper to
  get kWh for the Energy dashboard.
- **Primary sensor** — which temperature the climate entity shows:
  *Air* (default) or *Floor*. Both are always available as separate
  sensor entities.

## Entities

For each device:

- `climate.<name>` — main thermostat.
  - HVAC modes: Off, Heat (manual), Auto (schedule).
  - Presets: Schedule, Manual, Away (Away falls back to Manual on the
    local API — set via the Terneo app if you need the true scheduled
    away state).
- `sensor.<name>_floor_temperature`
- `sensor.<name>_air_temperature` *(disabled by default — enable it if
  you want it on the Lovelace temperature graph)*
- `sensor.<name>_power` *(only when **Heater power** is set)*

## Troubleshooting

**Entity goes unavailable / shows "Connection error"**

- Verify `http://<device-ip>/api.html` loads in your browser.
- Confirm you've unlocked local API access on the device.
- If the device is on a separate VLAN, make sure UDP 23500 (discovery)
  and TCP 80 (control) are reachable from your Home Assistant host.

**Writes have no effect / thermostat ignores commands**

- The device's LAN lock (`bLc`) is probably enabled. When the lock is on,
  read requests still work but writes are silently ignored unless they
  carry a valid TOTP token. Re-add the device and either fetch the TOTP
  key from the cloud or disable `bLc` on the device.

**Wrong temperature showing**

- The previous integration showed the floor sensor as "current
  temperature" regardless of configuration. This rewrite defaults to the
  air sensor; switch via **Settings → Devices & services → Terneo →
  Configure** if you heat floors only.

## Contributing

Issues and pull requests welcome.
