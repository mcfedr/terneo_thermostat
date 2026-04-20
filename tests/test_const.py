"""Sanity checks for constants that the rest of the integration depends on."""
from __future__ import annotations


def test_domain_matches_manifest(const_module, component_root) -> None:
    import json

    manifest = json.loads((component_root / "manifest.json").read_text())
    assert manifest["domain"] == const_module.DOMAIN


def test_primary_sensor_options(const_module) -> None:
    assert const_module.PRIMARY_AIR != const_module.PRIMARY_FLOOR
    assert {const_module.PRIMARY_AIR, const_module.PRIMARY_FLOOR} == {"air", "floor"}


def test_mode_constants_are_distinct(const_module) -> None:
    modes = {
        const_module.MODE_SCHEDULE,
        const_module.MODE_MANUAL,
        const_module.MODE_AWAY,
    }
    assert len(modes) == 3


def test_parameter_tuples_shape(const_module) -> None:
    for par in (const_module.PAR_POWER, const_module.PAR_MODE, const_module.PAR_SETPOINT):
        assert isinstance(par, tuple) and len(par) == 2
        assert all(isinstance(x, int) for x in par)


def test_temperature_bounds(const_module) -> None:
    assert const_module.MIN_TEMP < const_module.MAX_TEMP
    assert const_module.TEMP_STEP > 0


def test_default_scan_interval_sane(const_module) -> None:
    # Device broadcasts every ~30s; polling faster than 10s would stress it.
    assert 10 <= const_module.DEFAULT_SCAN_INTERVAL <= 120
