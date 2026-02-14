from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.goveelife.light import GoveeLifeLight
from tests.conftest import DIY_CAPABLE_FIXTURES, build_hass_data, load_device_fixture


def _create_light(hass, entry, coordinator, device_cfg):
    hass.data = build_hass_data(entry, coordinator, device_cfg)
    return GoveeLifeLight(hass, entry, coordinator, device_cfg, platform="light")


@pytest.mark.parametrize(
    "fixture_file", DIY_CAPABLE_FIXTURES, ids=[f.removesuffix(".json") for f in DIY_CAPABLE_FIXTURES]
)
@pytest.mark.asyncio
async def test_diy_scenes_loaded_and_deduplicated(hass, mock_config_entry, mock_coordinator, diy_scenes, fixture_file):
    device_cfg = load_device_fixture(fixture_file)
    light = _create_light(hass, mock_config_entry, mock_coordinator, device_cfg)

    with patch(
        "custom_components.goveelife.light.async_GoveeAPI_GetDynamicDIYScenes",
        new_callable=AsyncMock,
        return_value=diy_scenes,
    ):
        await light._async_update_diy_scenes()

    assert len(light._diy_scenes) == 4
    assert light._scene_value_map["DIY: Test DIY"] == {"value": 21747659, "type": "diy"}
    assert "DIY: New effect" in light._scene_value_map
    assert "DIY: New effect (2)" in light._scene_value_map
    assert "DIY: New effect (3)" in light._scene_value_map

    effects = light.effect_list
    assert effects[0].startswith("DIY: ")


@pytest.mark.parametrize(
    "fixture_file", DIY_CAPABLE_FIXTURES, ids=[f.removesuffix(".json") for f in DIY_CAPABLE_FIXTURES]
)
@pytest.mark.asyncio
async def test_diy_scene_activation(
    hass, mock_config_entry, mock_coordinator, diy_scenes, dynamic_scenes, fixture_file
):
    device_cfg = load_device_fixture(fixture_file)
    light = _create_light(hass, mock_config_entry, mock_coordinator, device_cfg)

    with (
        patch(
            "custom_components.goveelife.light.async_GoveeAPI_GetDynamicDIYScenes",
            new_callable=AsyncMock,
            return_value=diy_scenes,
        ),
        patch(
            "custom_components.goveelife.light.async_GoveeAPI_GetDynamicScenes",
            new_callable=AsyncMock,
            return_value=dynamic_scenes,
        ),
    ):
        await light._async_update_dynamic_scenes()
        await light._async_update_diy_scenes()

    with (
        patch(
            "custom_components.goveelife.light.async_GoveeAPI_ControlDevice",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_control,
        patch(
            "custom_components.goveelife.light.GoveeAPI_GetCachedStateValue",
            return_value=1,
        ),
    ):
        await light.async_turn_on(effect="DIY: Test DIY")

    diy_cap = mock_control.call_args_list[0][0][3]
    assert diy_cap["instance"] == "diyScene"
    assert diy_cap["value"] == 21747659

    with (
        patch(
            "custom_components.goveelife.light.async_GoveeAPI_ControlDevice",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_control,
        patch(
            "custom_components.goveelife.light.GoveeAPI_GetCachedStateValue",
            return_value=1,
        ),
    ):
        await light.async_turn_on(effect="Sunrise")

    regular_cap = mock_control.call_args_list[0][0][3]
    assert regular_cap["instance"] == "lightScene"
    assert regular_cap["value"] == 1001


@pytest.mark.parametrize(
    "fixture_file", DIY_CAPABLE_FIXTURES, ids=[f.removesuffix(".json") for f in DIY_CAPABLE_FIXTURES]
)
@pytest.mark.asyncio
async def test_diy_scenes_api_error(hass, mock_config_entry, mock_coordinator, fixture_file):
    device_cfg = load_device_fixture(fixture_file)
    light = _create_light(hass, mock_config_entry, mock_coordinator, device_cfg)

    with patch(
        "custom_components.goveelife.light.async_GoveeAPI_GetDynamicDIYScenes",
        new_callable=AsyncMock,
        side_effect=Exception("API timeout"),
    ):
        await light._async_update_diy_scenes()

    assert light._diy_scenes == []
    assert light.extra_state_attributes["diy_scenes_count"] == 0
