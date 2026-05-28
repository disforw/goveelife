"""Sensor entities for the Govee Life integration."""

from __future__ import annotations

import logging
import re
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_DEVICES,
    PERCENTAGE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import (
    HomeAssistant,
    callback,
)
from homeassistant.helpers.entity import EntityCategory

from .const import (
    CONF_COORDINATORS,
    DOMAIN,
)
from .entities import GoveeLifePlatformEntity
from .utils import GoveeAPI_GetCachedStateValue

_LOGGER: Final = logging.getLogger(__name__)
platform = "sensor"
platform_device_types = [
    "devices.types.sensor:.*",
    "devices.types.thermometer:.*",
    "devices.types.humidifier:devices.capabilities.property:sensorHumidity",
    "devices.types.humidifier:devices.capabilities.property:sensorTemperature",
    "devices.types.dehumidifier:devices.capabilities.property:sensorHumidity",
    "devices.types.dehumidifier:devices.capabilities.property:sensorTemperature",
    # Air quality monitors (H5140, CO2 monitors, etc.) — pure sensor devices
    "devices.types.air_quality_monitor:.*",
    # Air purifier read-only properties (airQuality, filterLifeTime on H7123, etc.)
    "devices.types.air_purifier:devices.capabilities.property:.*",
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the sensor platform."""
    _LOGGER.debug("Setting up %s platform entry: %s | %s", platform, DOMAIN, entry.entry_id)
    entities = []

    try:
        _LOGGER.debug("%s - async_setup_entry %s: Getting cloud devices from data store", entry.entry_id, platform)
        entry_data = hass.data[DOMAIN][entry.entry_id]
        api_devices = entry_data[CONF_DEVICES]
    except Exception as e:
        _LOGGER.error(
            "%s - async_setup_entry %s: Getting cloud devices from data store failed: %s (%s.%s)",
            entry.entry_id,
            platform,
            str(e),
            e.__class__.__module__,
            type(e).__name__,
        )
        return False

    for device_cfg in api_devices:
        try:
            d = device_cfg.get("device")
            coordinator = entry_data[CONF_COORDINATORS][d]
            for capability in device_cfg.get("capabilities", []):
                r = (
                    device_cfg.get("type", STATE_UNKNOWN)
                    + ":"
                    + capability.get("type", STATE_UNKNOWN)
                    + ":"
                    + capability.get("instance", STATE_UNKNOWN)
                )
                setup = False
                for platform_match in platform_device_types:
                    if re.match(platform_match, r):
                        setup = True
                        break
                if setup:
                    _LOGGER.debug(
                        "%s - async_setup_entry %s: Setup capability: %s|%s|%s ",
                        entry.entry_id,
                        platform,
                        d,
                        capability.get("type", STATE_UNKNOWN).split(".")[-1],
                        capability.get("instance", STATE_UNKNOWN),
                    )
                    entity = GoveeLifeSensor(hass, entry, coordinator, device_cfg, platform=platform, cap=capability)
                    entities.append(entity)
        except Exception as e:
            _LOGGER.error(
                "%s - async_setup_entry %s: Setup device failed: %s (%s.%s)",
                entry.entry_id,
                platform,
                str(e),
                e.__class__.__module__,
                type(e).__name__,
            )
            return False

    _LOGGER.info("%s - async_setup_entry: setup %s %s entities", entry.entry_id, len(entities), platform)
    if not entities:
        return None
    async_add_entities(entities)


class GoveeLifeSensor(GoveeLifePlatformEntity):
    """Sensor class for Govee Life integration."""

    def _init_platform_specific(self, **kwargs):
        """Platform specific init actions"""
        capabilities = kwargs.get("cap")
        self._capability_name = capabilities.get("instance")
        self.uniqueid = self._identifier + "_" + self._entity_id + "_" + self._capability_name
        self._name = self._capability_name
        self._state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = None
        self._attr_native_unit_of_measurement = None

        if self._capability_name == "sensorHumidity":
            self._attr_device_class = SensorDeviceClass.HUMIDITY
            self._attr_native_unit_of_measurement = PERCENTAGE
        elif self._capability_name == "sensorTemperature":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            # The Govee API delivers sensorTemperature values in Fahrenheit regardless
            # of the device's market region. Declaring FAHRENHEIT here lets HA's built-in
            # unit conversion display the correct value in the user's preferred unit
            # (°C or °F) without any manual conversion in this integration.
            # Note: we have not confirmed whether devices sold outside the US also
            # report in °F — if reports indicate otherwise this may need revisiting.
            self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
        elif self._capability_name == "carbonDioxideConcentration":
            self._attr_device_class = SensorDeviceClass.CO2
            self._attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
        elif self._capability_name == "airQuality":
            self._attr_device_class = SensorDeviceClass.AQI
            self._attr_native_unit_of_measurement = None
        elif self._capability_name == "filterLifeTime":
            self._attr_device_class = None
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state_class(self) -> SensorStateClass | None:
        """Return the state_class of the entity."""
        _LOGGER.debug("%s - %s: state_class: property requested", self._api_id, self._identifier)
        return self._state_class

    @property
    def capability_attributes(self):
        if self.state_class is not None:
            return {"state_class": self.state_class}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def state(self) -> str | None:
        """Return the current state of the entity."""
        value = GoveeAPI_GetCachedStateValue(
            self.hass,
            self._entry_id,
            self._device_cfg.get("device"),
            "devices.capabilities.property",
            self._capability_name,
        )
        _LOGGER.debug("%s - %s: state value: %s", self._api_id, self._identifier, value)
        return value
