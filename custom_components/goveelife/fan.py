"""Sensor entities for the Govee Life integration."""

from __future__ import annotations
from typing import Final
import logging
import asyncio
import math

from homeassistant.core import (
    HomeAssistant,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from homeassistant.components.fan import (FanEntity, FanEntityFeature)
from homeassistant.const import (
    CONF_DEVICES,
    STATE_ON,
    STATE_OFF,
    STATE_UNKNOWN,
)

from .entities import (
    GoveeLifePlatformEntity,
)

from .const import (
    DOMAIN,
    CONF_COORDINATORS,
)

from .utils import (
    GoveeAPI_GetCachedStateValue,
    async_GoveeAPI_ControlDevice,
)

_LOGGER: Final = logging.getLogger(__name__)
platform='fan'
platform_device_types = [ 'devices.types.air_purifier' ]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the fan platform."""
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
            if not device_cfg.get('type',STATE_UNKNOWN) in platform_device_types:
                continue      
            d=device_cfg.get('device')
            _LOGGER.debug("%s - async_setup_entry %s: Setup device: %s", entry.entry_id, platform, d) 
            coordinator = entry_data[CONF_COORDINATORS][d]
            entity=GoveeLifeFan(hass, entry, coordinator, device_cfg, platform=platform)
            entites.append(entity)
            await asyncio.sleep(0)
        except Exception as e:
            _LOGGER.error("%s - async_setup_entry %s: Setup device failed: %s (%s.%s)", entry.entry_id, platform, str(e), e.__class__.__module__, type(e).__name__)
            return False

    _LOGGER.info("%s - async_setup_entry: setup %s %s entities", entry.entry_id, len(entites), platform)
    if not entites:
        return None
    async_add_entities(entites)


class GoveeLifeFan(FanEntity, GoveeLifePlatformEntity):
    """Fan class for Govee Life integration."""

    _state_mapping = {}
    _state_mapping_set = {}
    _attr_preset_modes = []
    _attr_preset_modes_mapping = {}
    _attr_preset_modes_mapping_set = {}

    def _init_platform_specific(self, **kwargs):
        """Platform specific init actions"""
        _LOGGER.debug("%s - %s: _init_platform_specific", self._api_id, self._identifier)
        capabilities = self._device_cfg.get('capabilities',[])
 
        _LOGGER.debug("%s - %s: _init_platform_specific: processing devices request capabilities", self._api_id, self._identifier)
        for cap in capabilities:
            _LOGGER.debug("%s - %s: _init_platform_specific: processing cap: %s", self._api_id, self._identifier, cap)
            if cap['type'] == 'devices.capabilities.on_off':
                for option in cap['parameters']['options']:
                    if option['name'] == 'on':
                        self._state_mapping[option['value']] = STATE_ON
                        self._state_mapping_set[STATE_ON] = option['value']
                    elif option['name'] == 'off':
                        self._state_mapping[option['value']] = STATE_OFF
                        self._state_mapping_set[STATE_OFF] = option['value']
                    else:
                        _LOGGER.warning("%s - %s: _init_platform_specific: unhandled cap option: %s -> %s", self._api_id, self._identifier, cap['type'], option)
            elif cap['type'] == 'devices.capabilities.work_mode':
                self._attr_supported_features |= FanEntityFeature.PRESET_MODE
                for capFieldWork in cap['parameters']['fields']:
                    if not capFieldWork['fieldName'] == 'workMode':
                        continue                
                    for workOption in capFieldWork.get('options', []):
                        for capFieldValue in cap['parameters']['fields']:
                            if not capFieldValue['fieldName'] == 'modeValue':
                                continue
                            for valueOption in capFieldValue.get('options', []):
                                if not valueOption['name'] == workOption['name']:
                                    continue
                                if valueOption.get('options', None) is None: 
                                    v=str(workOption['value'])+':'+str(valueOption['defaultValue'])
                                    self._attr_preset_modes += [ workOption['name'] ]
                                    self._attr_preset_modes_mapping[v] = workOption['name']
                                    self._attr_preset_modes_mapping_set[workOption['name']] = { "workMode" : workOption['value'], "modeValue" : valueOption['defaultValue'] }
                                else:
                                    for valueOptionOption in valueOption.get('options', []):
                                        n=str(workOption['name'])+':'+str(valueOptionOption['name'])
                                        v=str(workOption['value'])+':'+str(valueOptionOption['value'])
                                        self._attr_preset_modes += [ n ]
                                        self._attr_preset_modes_mapping[v] = n
                                        self._attr_preset_modes_mapping_set[n] = { "workMode" : workOption['value'], "modeValue" : valueOptionOption['value'] }
            else:
                _LOGGER.debug("%s - %s: _init_platform_specific: cap unhandled: %s", self._api_id, self._identifier, cap)


    @property
    def state(self) -> str | None:
        """Return the current state of the entity."""
        value = GoveeAPI_GetCachedStateValue(self.hass, self._entry_id, self._device_cfg.get('device'), 'devices.capabilities.on_off', 'powerSwitch')
        v = self._state_mapping.get(value,STATE_UNKNOWN)
        if v == STATE_UNKNOWN:
            _LOGGER.warning("%s - %s: state: invalid value: %s", self._api_id, self._identifier, value)
            _LOGGER.debug("%s - %s: state: valid are: %s", self._api_id, self._identifier, self._state_mapping)
        return v

    @property
    def is_on(self) -> bool:
        """Return true if entity is on."""
        if self.state == STATE_ON: 
           return True
        return False

    #async def async_turn_on(self, **kwargs) -> None:
    async def async_turn_on(self, speed: str = None, mode: str = None, **kwargs) -> None:
        """Async: Turn entity on"""
        try:
            _LOGGER.debug("%s - %s: async_turn_on", self._api_id, self._identifier)
            _LOGGER.debug("%s - %s: async_turn_on: kwargs = %s", self._api_id, self._identifier, kwargs)
            if not self.is_on:
                state_capability = {
                    "type": "devices.capabilities.on_off",
                    "instance": 'powerSwitch',
                    "value": self._state_mapping_set[STATE_ON]
                    }
                if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
                    self.async_write_ha_state()
            else:
                _LOGGER.debug("%s - %s: async_turn_on: device already on", self._api_id, self._identifier)
            return None
        except Exception as e:
            _LOGGER.error("%s - %s: async_turn_on failed: %s (%s.%s)", self._api_id, self._identifier, str(e), e.__class__.__module__, type(e).__name__)

    async def async_turn_off(self, **kwargs) -> None:
        """Async: Turn entity off"""
        try:
            _LOGGER.debug("%s - %s: async_turn_off", self._api_id, self._identifier)
            _LOGGER.debug("%s - %s: async_turn_off: kwargs = %s", self._api_id, self._identifier, kwargs)
            if self.is_on:
                state_capability = {
                    "type": "devices.capabilities.on_off",
                    "instance": 'powerSwitch',
                    "value": self._state_mapping_set[STATE_OFF]
                    }
                if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
                    self.async_write_ha_state()
            else:
                _LOGGER.debug("%s - %s: async_turn_on: device already off", self._api_id, self._identifier)
            return None            
        except Exception as e:
            _LOGGER.error("%s - %s: async_turn_off failed: %s (%s.%s)", self._api_id, self._identifier, str(e), e.__class__.__module__, type(e).__name__)
