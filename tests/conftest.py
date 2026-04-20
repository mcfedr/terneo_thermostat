"""Shared fixtures and import helpers for the Terneo test suite.

These tests run under the ``Validate`` CI workflow with only pytest,
pytest-asyncio and pytest-cov installed (no Home Assistant). To keep the
suite useful in that environment we avoid importing the integration as a
Python package and instead load individual modules that don't pull in
``homeassistant.*`` at import time.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
from typing import Any

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
COMPONENT_ROOT = REPO_ROOT / "custom_components" / "terneo"


def _load_module(name: str, path: pathlib.Path) -> types.ModuleType:
    """Load a single .py file as a module without executing its package __init__."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def component_root() -> pathlib.Path:
    return COMPONENT_ROOT


@pytest.fixture(scope="session")
def repo_root() -> pathlib.Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def const_module() -> Any:
    """Load ``custom_components/terneo/const.py`` in isolation."""
    return _load_module("terneo_const", COMPONENT_ROOT / "const.py")
