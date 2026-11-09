from __future__ import annotations

import pytest
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import CONF_STATE, UnitOfTemperature

from custom_components.goveelife.const import DOMAIN
from custom_components.goveelife.sensor import GoveeLifeSensor
from tests.conftest import build_hass_data

DEVICE_CFG = {
    "sku": "H5179",
    "device": "AA:BB:CC:DD:EE:FF:00:11",
    "deviceName": "Wifi Thermometer",
    "type": "devices.types.thermometer",
    "capabilities": [
        {"type": "devices.capabilities.property", "instance": "sensorTemperature"},
        {"type": "devices.capabilities.property", "instance": "sensorHumidity"},
    ],
}


def _create_sensor(hass, entry, coordinator, instance, value):
    hass.data = build_hass_data(entry, coordinator, DEVICE_CFG)
    hass.data[DOMAIN][entry.entry_id][CONF_STATE] = {
        DEVICE_CFG["device"]: {
            "capabilities": [
                {
                    "type": "devices.capabilities.property",
                    "instance": instance,
                    "state": {"value": value},
                }
            ]
        }
    }
    cap = {"type": "devices.capabilities.property", "instance": instance}
    return GoveeLifeSensor(hass, entry, coordinator, DEVICE_CFG, platform="sensor", cap=cap)


def test_state_uses_sensor_entity_conversion():
    """Issue #152: overriding `state` bypassed HA's °F -> °C conversion."""
    assert GoveeLifeSensor.state is SensorEntity.state


def test_temperature_declares_fahrenheit(hass, mock_config_entry, mock_coordinator):
    sensor = _create_sensor(hass, mock_config_entry, mock_coordinator, "sensorTemperature", 77.36)

    assert sensor.device_class == SensorDeviceClass.TEMPERATURE
    assert sensor.native_unit_of_measurement == UnitOfTemperature.FAHRENHEIT
    assert sensor.native_value == pytest.approx(77.36)


def test_temperature_converted_to_user_unit(hass, mock_config_entry, mock_coordinator):
    sensor = _create_sensor(hass, mock_config_entry, mock_coordinator, "sensorTemperature", 77.36)
    # what HA sets when the user (or a metric system) selects °C for the entity
    sensor._sensor_option_unit_of_measurement = UnitOfTemperature.CELSIUS

    assert sensor.unit_of_measurement == UnitOfTemperature.CELSIUS
    assert float(sensor.state) == pytest.approx(25.2, abs=0.1)


@pytest.mark.parametrize(("raw", "expected"), [("45.5", 45.5), (None, None), ("", None), ("n/a", None)])
def test_numeric_values_are_coerced(hass, mock_config_entry, mock_coordinator, raw, expected):
    sensor = _create_sensor(hass, mock_config_entry, mock_coordinator, "sensorHumidity", raw)

    assert sensor.native_value == expected
