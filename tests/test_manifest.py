"""Manifest / HACS metadata validation.

These run under plain pytest with no Home Assistant installed, which is
useful catch-early insurance: the ``hassfest`` CI job covers the full HA
rules, but a broken JSON file will fail pytest here first.
"""
from __future__ import annotations

import json
import re


def test_manifest_json_valid(component_root) -> None:
    manifest = json.loads((component_root / "manifest.json").read_text())

    for key in (
        "domain",
        "name",
        "version",
        "documentation",
        "issue_tracker",
        "codeowners",
        "config_flow",
        "iot_class",
        "integration_type",
    ):
        assert key in manifest, f"manifest.json missing required key: {key}"

    assert manifest["domain"] == "terneo"
    assert manifest["config_flow"] is True
    assert manifest["iot_class"] == "local_polling"
    assert manifest["integration_type"] == "device"
    assert isinstance(manifest["codeowners"], list) and manifest["codeowners"]
    # Version is x.y.z semver-ish
    assert re.match(r"^\d+\.\d+\.\d+", manifest["version"])


def test_repo_urls_point_to_fork(component_root) -> None:
    manifest = json.loads((component_root / "manifest.json").read_text())
    assert "mcfedr/homeassistant-terneo-integration" in manifest["documentation"]
    assert "mcfedr/homeassistant-terneo-integration" in manifest["issue_tracker"]


def test_hacs_json_valid(repo_root) -> None:
    hacs = json.loads((repo_root / "hacs.json").read_text())
    assert "name" in hacs
    assert hacs.get("content_in_root", False) is False


def test_strings_and_translation_in_sync(component_root) -> None:
    strings = json.loads((component_root / "strings.json").read_text())
    en = json.loads((component_root / "translations" / "en.json").read_text())

    def shape(node):
        if isinstance(node, dict):
            return {k: shape(v) for k, v in node.items()}
        return None

    assert shape(strings) == shape(en), (
        "strings.json and translations/en.json must have matching keys"
    )
