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
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

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
    ("fixture_file", "instance", "state", "expected"),
    [
        # heater: the setpoint lives under the targetTemperature instance
        ("h7130_2024-07-10.json", "targetTemperature", {"unit": "Fahrenheit", "targetTemperature": 66}, 66),
        # kettle: the setpoint lives under the sliderTemperature instance
        ("h7170_2025-05-31.json", "sliderTemperature", {"unit": "Fahrenheit", "targetTemperature": 200}, 200),
    ],
)
def test_target_temperature_reads_the_instance_the_device_exposes(fixture_file, instance, state, expected):
    """The setpoint must be read from the device's own temperature_setting instance."""
    device_cfg = _load_device_fixture(fixture_file)

    with patch("custom_components.goveelife.climate.GoveeAPI_GetCachedStateValue") as cached:
        cached.side_effect = lambda hass, entry_id, device, cap_type, inst: state if inst == instance else None
        climate = _create_climate(device_cfg)

        assert climate.target_temperature == expected


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

        assert climate.native_temperature_unit == expected_unit
        assert climate.min_temp == expected_min
        assert climate.max_temp == expected_max


@pytest.mark.parametrize(
    ("cached_state", "expected_unit"),
    [
        # normal case: the unit is read back from the device's cached state
        ({"targetTemperature": 200, "unit": "Fahrenheit"}, "Fahrenheit"),
        # no cached state: fall back to the unit the entity reports, which is
        # itself Celsius in this situation - value and unit stay consistent
        (None, "Celsius"),
    ],
)
async def test_set_temperature_uses_the_instance_the_device_exposes(cached_state, expected_unit):
    """The H7170 exposes only sliderTemperature; setting must not assume targetTemperature."""
    device_cfg = _load_device_fixture("h7170_2025-05-31.json")

    with patch("custom_components.goveelife.climate.GoveeAPI_GetCachedStateValue") as cached:
        cached.return_value = {"targetTemperature": 212, "unit": "Fahrenheit"}
        climate = _create_climate(device_cfg)

        cached.return_value = cached_state
        with patch(
            "custom_components.goveelife.climate.async_GoveeAPI_ControlDevice",
            new=AsyncMock(return_value=True),
        ) as control:
            climate.async_write_ha_state = MagicMock()
            await climate.async_set_temperature(temperature=200)

    sent = control.await_args.args[3]
    assert sent["instance"] == "sliderTemperature"
    assert sent["value"] == {"temperature": 200, "unit": expected_unit}


def test_heater_attributes_rendered_in_fahrenheit():
    """The H7130 declares 5-30 Celsius but reports Fahrenheit; HA must show the same values as before."""
    device_cfg = _load_device_fixture("h7130_2024-07-10.json")
    cached_states = {
        "targetTemperature": {"temperature": 70, "unit": "Fahrenheit"},
        "sensorTemperature": 68,
    }

    with patch("custom_components.goveelife.climate.GoveeAPI_GetCachedStateValue") as cached:
        cached.side_effect = lambda hass, entry_id, device, cap_type, instance: cached_states.get(instance)
        climate = _create_climate(device_cfg)
        climate.hass.config.units = US_CUSTOMARY_SYSTEM

        assert climate.native_temperature_unit == UnitOfTemperature.FAHRENHEIT
        attributes = {**climate.capability_attributes, **climate.state_attributes}

    assert attributes["min_temp"] == 41
    assert attributes["max_temp"] == 86
    assert attributes["target_temp_step"] == 1
    assert attributes["current_temperature"] == 68
