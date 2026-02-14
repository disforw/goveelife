from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import CONF_API_KEY, CONF_DEVICES, CONF_FRIENDLY_NAME, CONF_PARAMS, CONF_SCAN_INTERVAL, CONF_TIMEOUT

from custom_components.goveelife.const import CONF_COORDINATORS, DOMAIN

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DEVICE_RESPONSES_DIR = FIXTURES_DIR / "device_responses"


def load_fixture(filename: str):
    return json.loads((FIXTURES_DIR / filename).read_text())


def load_device_fixture(filename: str):
    return json.loads((DEVICE_RESPONSES_DIR / filename).read_text())


DEVICE_FIXTURES = sorted(p.name for p in DEVICE_RESPONSES_DIR.glob("*.json"))

LIGHT_FIXTURES = [
    f for f in DEVICE_FIXTURES
    if load_device_fixture(f).get("type") == "devices.types.light"
]

DIY_CAPABLE_FIXTURES = [
    f for f in LIGHT_FIXTURES
    if any(c.get("instance") == "diyScene" for c in load_device_fixture(f).get("capabilities", []))
]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def diy_scenes():
    return load_fixture("diy_scenes_response.json")


@pytest.fixture
def dynamic_scenes():
    return load_fixture("dynamic_scenes_response.json")


@pytest.fixture
def mock_config_entry():
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        CONF_FRIENDLY_NAME: "GoveeLife",
        CONF_API_KEY: "fake-api-key",
    }
    return entry


@pytest.fixture
def mock_coordinator():
    coordinator = MagicMock()
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


def build_hass_data(entry, coordinator, device_cfg):
    return {
        DOMAIN: {
            entry.entry_id: {
                CONF_DEVICES: [device_cfg],
                CONF_COORDINATORS: {
                    device_cfg["device"]: coordinator,
                },
                CONF_PARAMS: {
                    CONF_API_KEY: "fake-api-key",
                    CONF_SCAN_INTERVAL: 60,
                    CONF_TIMEOUT: 10,
                },
            }
        }
    }
