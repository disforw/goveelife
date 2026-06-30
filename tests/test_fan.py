from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.fan import FanEntityFeature
from homeassistant.const import CONF_API_KEY, CONF_DEVICES, CONF_PARAMS, CONF_SCAN_INTERVAL, CONF_TIMEOUT

from custom_components.goveelife.const import CONF_COORDINATORS, DOMAIN
from custom_components.goveelife.fan import GoveeLifeFan

DEVICE_RESPONSES_DIR = Path(__file__).parent / "fixtures" / "device_responses"


def _load_device_fixture(fixture_file):
    return json.loads((DEVICE_RESPONSES_DIR / fixture_file).read_text())


def _create_fan(device_cfg):
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
    return GoveeLifeFan(hass, entry, coordinator, device_cfg, platform="fan")


@pytest.mark.parametrize(
    ("fixture_file", "speed_count"),
    [
        ("h7106_2026-06-30.json", 8),
        ("h7107_2025-08-28.json", 12),
    ],
)
def test_fanspeed_mode_values_are_used_as_discrete_speeds(fixture_file, speed_count):
    device_cfg = _load_device_fixture(fixture_file)

    fan = _create_fan(device_cfg)

    assert fan.supported_features & FanEntityFeature.SET_SPEED
    assert fan.speed_count == speed_count
    assert fan.percentage_step == pytest.approx(100 / speed_count)
    assert fan.preset_modes == ["Off", "FanSpeed", "Auto", "Sleep", "Nature", "Custom"]
    assert fan._ordered_named_fan_speeds == [f"Speed {speed}" for speed in range(1, speed_count + 1)]
    assert fan._attr_preset_modes_mapping_set["FanSpeed"] == {"workMode": 1, "modeValue": speed_count}
