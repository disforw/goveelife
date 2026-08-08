from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import (
    CONF_API_KEY,
    CONF_DEVICES,
    CONF_PARAMS,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    UnitOfTemperature,
)

from custom_components.goveelife.climate import GoveeLifeClimate
from custom_components.goveelife.const import CONF_COORDINATORS, DOMAIN

DEVICE_RESPONSES_DIR = Path(__file__).parent / "fixtures" / "device_responses"


def _load_device_fixture(fixture_file):
    return json.loads((DEVICE_RESPONSES_DIR / fixture_file).read_text())


def _create_climate(device_cfg):
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    coordinator = MagicMock()
    coordinator.async_request_refresh = AsyncMock()
    hass.data = {
        DOMAIN: {
            entry.entry_id: {
                CONF_DEVICES: [device_cfg],
                CONF_COORDINATORS: {device_cfg["device"]: coordinator},
                CONF_PARAMS: {
                    CONF_API_KEY: "fake-api-key",
                    CONF_SCAN_INTERVAL: 60,
                    CONF_TIMEOUT: 10,
                },
            }
        }
    }
    return GoveeLifeClimate(hass, entry, coordinator, device_cfg, platform="climate")


@pytest.mark.parametrize(
    ("reported_unit", "expected_unit", "expected_min", "expected_max"),
    [
        ("Fahrenheit", UnitOfTemperature.FAHRENHEIT, 104, 212),
        ("Celsius", UnitOfTemperature.CELSIUS, 40, 100),
    ],
)
def test_kettle_bounds_follow_reported_unit(reported_unit, expected_unit, expected_min, expected_max):
    """The H7170 declares its 40-100 range in Celsius; bounds must match the reported unit."""
    device_cfg = _load_device_fixture("h7170_2025-05-31.json")

    with patch("custom_components.goveelife.climate.GoveeAPI_GetCachedStateValue") as cached:
        cached.return_value = {"targetTemperature": 212, "unit": reported_unit}
        climate = _create_climate(device_cfg)

        assert climate.temperature_unit == expected_unit
        assert climate.min_temp == expected_min
        assert climate.max_temp == expected_max
