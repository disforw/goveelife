from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.light import ColorMode
from homeassistant.const import STATE_OFF, STATE_ON

from custom_components.goveelife.light import GoveeLifeNightLight, has_nightlight_light
from custom_components.goveelife.switch import _has_on_off_options
from tests.conftest import build_hass_data, load_device_fixture

NIGHTLIGHT_FIXTURES = ["h7129_2025-11-22.json", "h7140_2025-12-31.json"]
CACHED = "custom_components.goveelife.light.GoveeAPI_GetCachedStateValue"
CONTROL = "custom_components.goveelife.light.async_GoveeAPI_ControlDevice"


def _create(hass, entry, coordinator, fixture):
    device_cfg = load_device_fixture(fixture)
    hass.data = build_hass_data(entry, coordinator, device_cfg)
    light = GoveeLifeNightLight(hass, entry, coordinator, device_cfg, platform="light")
    light.async_write_ha_state = MagicMock()
    return light


@pytest.mark.parametrize("fixture", NIGHTLIGHT_FIXTURES)
def test_nightlight_detected(fixture):
    assert has_nightlight_light(load_device_fixture(fixture))


def test_toggle_only_nightlight_not_detected():
    device_cfg = {
        "type": "devices.types.humidifier",
        "capabilities": [{"type": "devices.capabilities.toggle", "instance": "nightlightToggle"}],
    }
    assert not has_nightlight_light(device_cfg)


@pytest.mark.parametrize("fixture", NIGHTLIGHT_FIXTURES)
def test_nightlight_entity(hass, mock_config_entry, mock_coordinator, fixture):
    """Issues #163 / #149: appliance nightlights get brightness and colour."""
    light = _create(hass, mock_config_entry, mock_coordinator, fixture)

    assert light.unique_id.endswith("_nightlight")
    assert light.name.endswith("Nightlight")
    assert light.entity_id.endswith("_nightlight")
    assert light._support_brightness
    assert ColorMode.RGB in light.supported_color_modes
    assert light._power_cap_instance == "nightlightToggle"

    with patch(CACHED, return_value=1):
        assert light.state == STATE_ON
    with patch(CACHED, return_value=0):
        assert light.state == STATE_OFF


async def test_nightlight_turn_off_uses_toggle(hass, mock_config_entry, mock_coordinator):
    light = _create(hass, mock_config_entry, mock_coordinator, "h7140_2025-12-31.json")

    with patch(CONTROL, AsyncMock(return_value=True)) as ctrl:
        await light.async_turn_off()

    assert ctrl.call_args.args[3] == {
        "type": "devices.capabilities.toggle",
        "instance": "nightlightToggle",
        "value": 0,
    }


def test_switch_skips_non_on_off_toggles():
    """The ice maker iceMakingToggle (iceMaking/Clean) is not an on/off switch."""
    on_off = {"parameters": {"options": [{"name": "on", "value": 1}, {"name": "off", "value": 0}]}}
    clean = {"parameters": {"options": [{"name": "iceMaking", "value": 0}, {"name": "Clean", "value": 1}]}}

    assert _has_on_off_options(on_off)
    assert not _has_on_off_options(clean)
