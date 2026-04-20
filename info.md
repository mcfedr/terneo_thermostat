# Terneo Thermostat

Local-only Home Assistant integration for Terneo Wi-Fi thermostats
(terneo AX, SX, RX and similar models from DS Electronics / my.terneo.ua).

No cloud account required — the integration talks directly to the device
over your LAN using the documented
[Terneo local HTTP API](https://terneo-api.readthedocs.io/).

## Highlights

- **UI configuration** (no YAML).
- **Async** aiohttp client, non-blocking in Home Assistant.
- Proper handling of the device's `status=timeout` busy response.
- **Climate entity** with Off / Heat (manual) / Auto (schedule) modes.
- **Sensors**: floor temperature, air temperature, and — optionally — a
  power sensor that reports heater wattage when the relay is on. Feed it
  into a Riemann-sum / utility-meter helper to track kWh on the Energy
  dashboard.
- Pick which sensor (air or floor) the thermostat entity shows as
  "current temperature".

## Requirements

- Terneo Wi-Fi thermostat with firmware **2.3 or newer**.
- Local API unlocked on the device (default firmware 2.3 blocks it for
  security — see the
  [safety page](https://terneo-api.readthedocs.io/ru/latest/en/safety.html)
  of the API docs for the on-device setting).
- Device IP and serial number (serial is on the sticker and on
  `http://<device-ip>/index.html`).

## Setup

After installing via HACS and restarting Home Assistant, add the integration
from **Settings → Devices & services → Add integration → Terneo**.
