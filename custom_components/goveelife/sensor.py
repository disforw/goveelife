"""Sensor entities for the Govee Life integration."""

from __future__ import annotations
from typing import Final
import logging
import asyncio
import re

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import CONF_DEVICES, STATE_UNKNOWN

from .entities import GoveeLifePlatformEntity
from .const import DOMAIN, CONF_COORDINATORS
from .utils import async_ProgrammingDebug

_LOGGER: Final = logging.getLogger(__name__)
platform = 'sensor'
platform_device_types = [
    'devices.types.sensor:.*',
    'devices.types.thermometer:.*'
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
        _LOGGER.error("%s - async_setup_entry %s: Getting cloud devices from data store failed: %s (%s.%s)", entry.entry_id, platform, str(e), e.__class__.__module__, type(e).__name__)
        return False

    for device_cfg in api_devices:
        try:
            device = device_cfg.get('device')
            coordinator = entry_data[CONF_COORDINATORS][device]
            for capability in device_cfg.get('capabilities', []):
                capability_key = f"{device_cfg.get('type', STATE_UNKNOWN)}:{capability.get('type', STATE_UNKNOWN)}:{capability.get('instance', STATE_UNKNOWN)}"
                setup = any(re.match(platform_match, capability_key) for platform_match in platform_device_types)
                if setup:
                    _LOGGER.debug("%s - async_setup_entry %s: Setup capability: %s|%s|%s", entry.entry_id, platform, device, capability.get('type', STATE_UNKNOWN).split('.')[-1], capability.get('instance', STATE_UNKNOWN))
                    entity = GoveeLifeSensor(hass, entry, coordinator, device_cfg, platform=platform, cap=capability)
                    entities.append(entity)
            await asyncio.sleep(0)
        except Exception as e:
            _LOGGER.error("%s - async_setup_entry %s: Setup device failed: %s (%s.%s)", entry.entry_id, platform, str(e), e.__class__.__module__, type(e).__name__)
            return False

    _LOGGER.info("%s - async_setup_entry: setup %s %s entities", entry.entry_id, len(entities), platform)
    if not entities:
        return None
    async_add_entities(entities)


class GoveeLifeSensor(SensorEntity, GoveeLifePlatformEntity):
    """Sensor class for Govee Life integration."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, coordinator, device_cfg, platform, cap):
        """Initialize the sensor."""
        super().__init__(hass, entry, coordinator, device_cfg, platform=platform, cap=cap)
        self._state_class = None

    @property
    def state_class(self) -> SensorStateClass | None:
        """Return the state_class of the entity."""
        _LOGGER.debug("%s - %s: state_class: property requested", self._api_id, self._identifier)
        return self._state_class

    @property
    def capability_attributes(self):
        """Return capability attributes."""
        if self.state_class is not None:
            return {"state_class": self.state_class}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        d = self._device_cfg.get('device')
        self.hass.data[DOMAIN][self.entry.entry_id][CONF_STATE][d]
        self.async_write_ha_state()
