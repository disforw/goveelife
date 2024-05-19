"""Sensor entities for the Govee Life integration."""

from __future__ import annotations
from typing import Final
import logging
import asyncio
import re

from homeassistant.core import (
    HomeAssistant,
    callback,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import SensorStateClass
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import (
    CONF_DEVICES,
    STATE_UNKNOWN,
)

from .entities import GoveeLifePlatformEntity

from .const import (
    DOMAIN,
    CONF_COORDINATORS,
)
from .utils import (
    async_ProgrammingDebug,
)

_LOGGER: Final = logging.getLogger(__name__)
platform='sensor'
platform_device_types = [ 
    'devices.types.sensor:.*', 
    'devices.types.thermometer:.*' 
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the sensor platform."""
    _LOGGER.debug("Setting up %s platform entry: %s | %s", platform, DOMAIN, entry.entry_id)
    entites=[]
    
    
    try:
        _LOGGER.debug("%s - async_setup_entry %s: Getting cloud devices from data store", entry.entry_id, platform)
        entry_data=hass.data[DOMAIN][entry.entry_id]
        api_devices=entry_data[CONF_DEVICES]
    except Exception as e:
        _LOGGER.error("%s - async_setup_entry %s: Getting cloud devices from data store failed: %s (%s.%s)", entry.entry_id, platform, str(e), e.__class__.__module__, type(e).__name__)
        return False

    for device_cfg in api_devices:
        try:
            d=device_cfg.get('device')
            coordinator = entry_data[CONF_COORDINATORS][d]
            for capability in device_cfg.get('capabilities',[]):
                r=device_cfg.get('type',STATE_UNKNOWN)+':'+capability.get('type',STATE_UNKNOWN)+':'+capability.get('instance',STATE_UNKNOWN)
                setup=False
                for platform_match in platform_device_types:
                    if re.match(platform_match, r):
                        setup=True
                        break
                if setup:
                    _LOGGER.debug("%s - async_setup_entry %s: Setup capability: %s|%s|%s ", entry.entry_id, platform, d, capability.get('type',STATE_UNKNOWN).split('.')[-1], capability.get('instance',STATE_UNKNOWN))
                    entity=GoveeLifeSensor(hass, entry, coordinator, device_cfg, platform=platform, cap=capability)
                    entites.append(entity)
            await asyncio.sleep(0)
        except Exception as e:
            _LOGGER.error("%s - async_setup_entry %s: Setup device failed: %s (%s.%s)", entry.entry_id, platform, str(e), e.__class__.__module__, type(e).__name__)
            return False

    _LOGGER.info("%s - async_setup_entry: setup %s %s entities", entry.entry_id, len(entites), platform)
    if not entites:
        return None
    async_add_entities(entites)


class GoveeLifeSensor(GoveeLifePlatformEntity):
    """Sensor class for Govee Life integration."""

    def _init_platform_specific(self, **kwargs):
        """Platform specific init actions"""
        self._state_class = None

    @property
    def state_class(self) -> SensorStateClass | None:
        """Return the state_class of the entity."""
        _LOGGER.debug("%s - %s: state_class: property requested", self._api_id, self._identifier)
        return self._state_class

    @property
    def capability_attributes(self):
        if not self.state_class is None:
            return {"state_class": self.state_class}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        #self._attr_is_on = self.coordinator.data[self.idx]["state"]        
        d=self._device_cfg.get('device')
        self.hass.data[DOMAIN][entry.entry_id][CONF_STATE][d]
        self.async_write_ha_state()

