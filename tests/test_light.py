from __future__ import annotations

import pytest
from homeassistant.components.light import ColorMode, LightEntityFeature

from custom_components.goveelife.light import GoveeLifeLight
from tests.conftest import LIGHT_FIXTURES, build_hass_data, load_device_fixture


def _create_light(hass, entry, coordinator, device_cfg):
    return GoveeLifeLight(hass, entry, coordinator, device_cfg, platform="light")


@pytest.mark.parametrize("fixture_file", LIGHT_FIXTURES, ids=[f.removesuffix(".json") for f in LIGHT_FIXTURES])
def test_capability_detection(hass, mock_config_entry, mock_coordinator, fixture_file):
    device_cfg = load_device_fixture(fixture_file)
    hass.data = build_hass_data(mock_config_entry, mock_coordinator, device_cfg)
    light = _create_light(hass, mock_config_entry, mock_coordinator, device_cfg)

    caps = {c["type"] + "/" + c["instance"] for c in device_cfg["capabilities"]}

    assert bool(light._support_brightness) == ("devices.capabilities.range/brightness" in caps)
    assert bool(light._support_color) == ("devices.capabilities.color_setting/colorRgb" in caps)
    assert bool(light._support_color_temp) == ("devices.capabilities.color_setting/colorTemperatureK" in caps)

    has_light_scene = "devices.capabilities.dynamic_scene/lightScene" in caps
    assert bool(light._support_scenes) == has_light_scene
    assert bool(light._has_dynamic_scenes) == has_light_scene

    if has_light_scene:
        assert light.supported_features & LightEntityFeature.EFFECT

    if light._support_color and light._support_color_temp:
        assert ColorMode.RGB in light.supported_color_modes
        assert ColorMode.COLOR_TEMP in light.supported_color_modes
