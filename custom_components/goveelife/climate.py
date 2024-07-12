"""Sensor entities for the Govee Life integration."""

from __future__ import annotations
from typing import Final
import logging
import asyncio

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import (
    CONF_DEVICES,
    STATE_UNKNOWN,
    UnitOfTemperature,
)

from .entities import GoveeLifePlatformEntity
from .const import DOMAIN, CONF_COORDINATORS
from .utils import GoveeAPI_GetCachedStateValue, async_GoveeAPI_ControlDevice

_LOGGER: Final = logging.getLogger(__name__)
PLATFORM = 'climate'
PLATFORM_DEVICE_TYPES = ['devices.types.heater']

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the climate platform."""
    _LOGGER.debug("Setting up %s platform entry: %s | %s", PLATFORM, DOMAIN, entry.entry_id)
    entities = []

    try:
        entry_data = hass.data[DOMAIN][entry.entry_id]
        api_devices = entry_data[CONF_DEVICES]
    except Exception as e:
        _LOGGER.error("%s - async_setup_entry %s: Failed to get cloud devices from data store: %s (%s.%s)", entry.entry_id, PLATFORM, str(e), e.__class__.__module__, type(e).__name__)
        return

    for device_cfg in api_devices:
        try:
            if device_cfg.get('type') not in PLATFORM_DEVICE_TYPES:
                continue
            device = device_cfg.get('device')
            coordinator = entry_data[CONF_COORDINATORS][device]
            entity = GoveeLifeClimate(hass, entry, coordinator, device_cfg, platform=PLATFORM)
            entities.append(entity)
            await asyncio.sleep(0)
        except Exception as e:
            _LOGGER.error("%s - async_setup_entry %s: Failed to setup device: %s (%s.%s)", entry.entry_id, PLATFORM, str(e), e.__class__.__module__, type(e).__name__)
            return

    if entities:
        async_add_entities(entities)


class GoveeLifeClimate(ClimateEntity, GoveeLifePlatformEntity):
    """Climate class for Govee Life integration."""

    _attr_hvac_modes = []
    _attr_hvac_modes_mapping = {}
    _attr_hvac_modes_mapping_set = {}
    _attr_preset_modes = []
    _attr_preset_modes_mapping = {}
    _attr_preset_modes_mapping_set = {}
    _enable_turn_on_off_backwards_compatibility = False

    def _init_platform_specific(self, **kwargs):
        """Platform specific init actions."""
        _LOGGER.debug("%s - %s: _init_platform_specific", self._api_id, self._identifier)
        capabilities = self._device_cfg.get('capabilities', [])

        _LOGGER.debug("%s - %s: _init_platform_specific: processing devices request capabilities", self._api_id, self._identifier)
        for cap in capabilities:
            #_LOGGER.debug("%s - %s: _init_platform_specific: processing cap: %s", self._api_id, self._identifier, cap)
            if cap['type'] == 'devices.capabilities.on_off':
                for option in cap['parameters']['options']:
                    if option['name'] == 'on':
                        self._attr_supported_features |= ClimateEntityFeature.TURN_ON
                        self._attr_hvac_modes.append(HVACMode.HEAT_COOL)
                        self._attr_hvac_modes_mapping[option['value']] = HVACMode.HEAT_COOL
                        self._attr_hvac_modes_mapping_set[HVACMode.HEAT_COOL] = option['value']
                    elif option['name'] == 'off':
                        self._attr_supported_features |= ClimateEntityFeature.TURN_OFF
                        self._attr_hvac_modes.append(HVACMode.OFF)
                        self._attr_hvac_modes_mapping[option['value']] = HVACMode.OFF
                        self._attr_hvac_modes_mapping_set[HVACMode.OFF] = option['value']
                    else:
                        _LOGGER.warning("%s - %s: _init_platform_specific: unknown on_off option: %s", self._api_id, self._identifier, option)
            elif cap['type'] == 'devices.capabilities.temperature_setting' and cap['instance'] == 'targetTemperature':
                self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
                for field in cap['parameters']['fields']:
                    if field['fieldName'] == 'temperature':
                        self._attr_max_temp = field['range']['max']
                        self._attr_min_temp = field['range']['min']
                        self._attr_target_temperature_step = field['range']['precision']
                    elif field['fieldName'] == 'unit':
                        self._attr_temperature_unit = UnitOfTemperature[field['defaultValue'].upper()]
                    elif field['fieldName'] == 'autoStop':
                        pass #TO-BE-DONE: implement as switch entity type
            elif cap['type'] == 'devices.capabilities.work_mode':
                self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
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
            elif cap['type'] == 'devices.capabilities.property' and cap['instance'] == 'sensorTemperature':
                pass #do nothing as this is handled within 'current_temperature' property
            else:
                _LOGGER.debug("%s - %s: _init_platform_specific: cap unhandled: %s", self._api_id, self._identifier, cap)

    @property
    def hvac_mode(self) -> str:
        """Return the hvac_mode of the entity."""
        #_LOGGER.debug("%s - %s: hvac_mode", self._api_id, self._identifier)  
        value = GoveeAPI_GetCachedStateValue(self.hass, self._entry_id, self._device_cfg.get('device'), 'devices.capabilities.on_off', 'powerSwitch')
        v = self._attr_hvac_modes_mapping.get(value,STATE_UNKNOWN)
        if v == STATE_UNKNOWN:
            _LOGGER.warning("%s - %s: hvac_mode: invalid value: %s", self._api_id, self._identifier, value)
            _LOGGER.debug("%s - %s: hvac_mode: valid are: %s", self._api_id, self._identifier, self._state_mapping)
        return v

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        #_LOGGER.debug("%s - %s: async_set_hvac_mode", self._api_id, self._identifier) 
        state_capability = {
            "type": "devices.capabilities.on_off",
            "instance": "powerSwitch",
            "value": self._attr_hvac_modes_mapping_set[hvac_mode]
            }
        if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
            self.async_write_ha_state()
        return None

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.async_set_hvac_mode(HVACMode.HEATING)

    @property
    def preset_mode(self) -> str | None:
        """Return the preset_mode of the entity."""
        #_LOGGER.debug("%s - %s: preset_mode", self._api_id, self._identifier)  
        value = GoveeAPI_GetCachedStateValue(self.hass, self._entry_id, self._device_cfg.get('device'), 'devices.capabilities.work_mode', 'workMode')
        v=str(value['workMode'])+':'+str(value['modeValue'])
        v=self._attr_preset_modes_mapping.get(v,STATE_UNKNOWN)
        if v == STATE_UNKNOWN:
            _LOGGER.warning("%s - %s: preset_mode: invalid value: %s", self._api_id, self._identifier, value)
            _LOGGER.debug("%s - %s: preset_mode: valid are: %s", self._api_id, self._identifier, self._attr_preset_modes_mapping)
        return v 

    async def async_set_preset_mode(self, preset_mode) -> None:
        """Set new target preset mode."""
        #_LOGGER.debug("%s - %s: async_set_preset_mode", self._api_id, self._identifier)
        state_capability = {
            "type": "devices.capabilities.work_mode",
            "instance": "workMode",
            "value": self._attr_preset_modes_mapping_set[preset_mode]
            }
        if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
            self.async_write_ha_state()
        return None
    

    @property
    def temperature_unit(self) -> str:
        """Return the temperature unit of the entity."""
        value = GoveeAPI_GetCachedStateValue(self.hass, self._entry_id, self._device_cfg.get('device'), 'devices.capabilities.temperature_setting', 'targetTemperature')
        return UnitOfTemperature[value.get('unit', 'CELSIUS').upper()]

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature of the entity."""
        #_LOGGER.debug("%s - %s: target_temperature", self._api_id, self._identifier)
        value = GoveeAPI_GetCachedStateValue(self.hass, self._entry_id, self._device_cfg.get('device'), 'devices.capabilities.temperature_setting', 'targetTemperature')
        return value.get('targetTemperature', 0)

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""        
        #_LOGGER.debug("%s - %s: async_set_temperature", self._api_id, self._identifier)
        value = GoveeAPI_GetCachedStateValue(self.hass, self._entry_id, self._device_cfg.get('device'), 'devices.capabilities.temperature_setting', 'targetTemperature')
        unit = value.get('unit', 'Celsius')
        state_capability = {
            "type": "devices.capabilities.temperature_setting",
            "instance": "targetTemperature",
            "value": {
                "temperature": kwargs['temperature'],
                "unit": unit,
                }
            }
        if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
            self.async_write_ha_state()      
        return None


    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature of the entity."""
        #_LOGGER.debug("%s - %s: current_temperature", self._api_id, self._identifier)  
        value = GoveeAPI_GetCachedStateValue(self.hass, self._entry_id, self._device_cfg.get('device'), 'devices.capabilities.property', 'sensorTemperature')
        if self.temperature_unit == UnitOfTemperature.CELSIUS:
            #value seems to be always Fahrenheit - calculate to °C if necessary
            value = (value - 32) * 5 / 9
        return value


