from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.goveelife.humidifier import GoveeLifeHumidifier
from tests.conftest import build_hass_data, load_device_fixture

CACHED = "custom_components.goveelife.humidifier.GoveeAPI_GetCachedStateValue"
CONTROL = "custom_components.goveelife.humidifier.async_GoveeAPI_ControlDevice"


def _create(hass, entry, coordinator, fixture="h7140_2025-12-31.json"):
    device_cfg = load_device_fixture(fixture)
    hass.data = build_hass_data(entry, coordinator, device_cfg)
    entity = GoveeLifeHumidifier(hass, entry, coordinator, device_cfg, platform="humidifier")
    entity.async_write_ha_state = MagicMock()
    return entity


def _cached(values):
    return lambda hass, entry_id, device, cap_type, instance: values.get(instance)


def test_mode_reflects_cached_work_mode(hass, mock_config_entry, mock_coordinator):
    entity = _create(hass, mock_config_entry, mock_coordinator)
    name, mapping = next(iter(entity._attr_preset_modes_mapping_set.items()))

    with patch(CACHED, side_effect=_cached({"workMode": dict(mapping)})):
        assert entity.mode == name


def test_target_humidity_reads_range_state(hass, mock_config_entry, mock_coordinator):
    entity = _create(hass, mock_config_entry, mock_coordinator)

    with patch(CACHED, side_effect=_cached({"humidity": 55})):
        assert entity.target_humidity == 55.0


@pytest.mark.parametrize("call", ["positional", "keyword"])
async def test_set_mode_accepts_positional_and_keyword(hass, mock_config_entry, mock_coordinator, call):
    entity = _create(hass, mock_config_entry, mock_coordinator)
    name, mapping = next(iter(entity._attr_preset_modes_mapping_set.items()))

    with patch(CONTROL, AsyncMock(return_value=True)) as ctrl:
        if call == "positional":
            await entity.async_set_mode(name)
        else:
            await entity.async_set_mode(mode=name)

    assert ctrl.call_args.args[3]["value"] == mapping


async def test_set_mode_ignores_unknown_mode(hass, mock_config_entry, mock_coordinator):
    entity = _create(hass, mock_config_entry, mock_coordinator)

    with patch(CONTROL, AsyncMock(return_value=True)) as ctrl:
        await entity.async_set_mode("does-not-exist")

    ctrl.assert_not_called()
