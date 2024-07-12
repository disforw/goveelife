"""Sensor entities for the Govee Life integration."""

from __future__ import annotations
from typing import Final
import logging
import asyncio
import math

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util.color import brightness_to_value, value_to_brightness
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.const import (
    CONF_DEVICES,
    STATE_ON,
    STATE_OFF,
    STATE_UNKNOWN,
)

from .entities import GoveeLifePlatformEntity
from .const import DOMAIN, CONF_COORDINATORS
from .utils import GoveeAPI_GetCachedStateValue, async_GoveeAPI_ControlDevice

_LOGGER: Final = logging.getLogger(__name__)
platform = 'light'
platform_device_types = ['devices.types.light']

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up the light platform."""
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
            if not device_cfg.get('type', STATE_UNKNOWN) in platform_device_types:
                continue      
            d = device_cfg.get('device')
            _LOGGER.debug("%s - async_setup_entry %s: Setup device: %s", entry.entry_id, platform, d) 
            coordinator = entry_data[CONF_COORDINATORS][d]
            entity = GoveeLifeLight(hass, entry, coordinator, device_cfg, platform=platform)
            entities.append(entity)
            await asyncio.sleep(0)
        except Exception as e:
            _LOGGER.error("%s - async_setup_entry %s: Setup device failed: %s (%s.%s)", entry.entry_id, platform, str(e), e.__class__.__module__, type(e).__name__)
            return False

    _LOGGER.info("%s - async_setup_entry: setup %s %s entities", entry.entry_id, len(entities), platform)
    if not entities:
        return None
    async_add_entities(entities)

class GoveeLifeLight(LightEntity, GoveeLifePlatformEntity):
    """Light class for Govee Life integration."""

    _state_mapping = {}
    _state_mapping_set = {}
    _attr_supported_color_modes = set()

    def _init_platform_specific(self, **kwargs):
        """Platform specific init actions"""
        _LOGGER.debug("%s - %s: _init_platform_specific", self._api_id, self._identifier)
        capabilities = self._device_cfg.get('capabilities', [])

        _LOGGER.debug("%s - %s: _init_platform_specific: processing devices request capabilities", self._api_id, self._identifier)
        for cap in capabilities:
            if cap['type'] == 'devices.capabilities.on_off':
                self._attr_supported_color_modes.add(ColorMode.ONOFF)
                for option in cap['parameters']['options']:
                    if option['name'] == 'on':
                        self._state_mapping[option['value']] = STATE_ON
                        self._state_mapping_set[STATE_ON] = option['value']
                    elif option['name'] == 'off':
                        self._state_mapping[option['value']] = STATE_OFF
                        self._state_mapping_set[STATE_OFF] = option['value']
                    else:
                        _LOGGER.warning("%s - %s: _init_platform_specific: unhandled cap option: %s -> %s", self._api_id, self._identifier, cap['type'], option)
            elif cap['type'] == 'devices.capabilities.range' and cap['instance'] == 'brightness':
                self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)
                self._brightness_scale = (cap['parameters']['range']['min'], cap['parameters']['range']['max'])
            elif cap['type'] == 'devices.capabilities.color_setting' and cap['instance'] == 'colorRgb':
                self._attr_supported_color_modes.add(ColorMode.RGB)
            elif cap['type'] == 'devices.capabilities.color_setting' and cap['instance'] == 'colorTemperatureK':
                self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)
                self._attr_min_color_temp_kelvin = cap['parameters']['range']['min']
                self._attr_max_color_temp_kelvin = cap['parameters']['range']['max']
            elif cap['type'] == 'devices.capabilities.toggle' and cap['instance'] == 'gradientToggle':
                pass  # implemented as switch entity type
            elif cap['type'] == 'devices.capabilities.segment_color_setting':
                pass  # TO-BE-DONE - implement as service?
            elif cap['type'] == 'devices.capabilities.dynamic_scene':
                pass  # TO-BE-DONE: implement as select entity type
            elif cap['type'] == 'devices.capabilities.music_setting':
                pass  # TO-BE-DONE: implement as select entity type
            elif cap['type'] == 'devices.capabilities.dynamic_setting':
                pass  # TO-BE-DONE: implement as select ? unsure about setting effect
            else:
                _LOGGER.debug("%s - %s: _init_platform_specific: cap unhandled: %s", self._api_id, self._identifier, cap)

    def _getRGBfromI(self, RGBint):
        blue = RGBint & 255
        green = (RGBint >> 8) & 255
        red = (RGBint >> 16) & 255
        return red, green, blue

    def _getIfromRGB(self, rgb):
        red = rgb[0]
        green = rgb[1]
        blue = rgb[2]
        RGBint = (red << 16) + (green << 8) + blue
        return RGBint

    @property
    def state(self) -> str | None:
        """Return the current state of the entity."""
        value = GoveeAPI_GetCachedStateValue(self.hass, self._entry_id, self._device_cfg.get('device'), 'devices.capabilities.on_off', 'powerSwitch')
        v = self._state_mapping.get(value, STATE_UNKNOWN)
        if v == STATE_UNKNOWN:
            _LOGGER.warning("%s - %s: state: invalid value: %s", self._api_id, self._identifier, value)
            _LOGGER.debug("%s - %s: state: valid are: %s", self._api_id, self._identifier, self._state_mapping)
        return v

    @property
    def is_on(self) -> bool:
        """Return true if entity is on."""
        return self.state == STATE_ON

    @property
    def brightness(self) -> int | None:
        """Return the current brightness."""
        value = GoveeAPI_GetCachedStateValue(self.hass, self._entry_id, self._device_cfg.get('device'), 'devices.capabilities.range', 'brightness')
        return value_to_brightness(self._brightness_scale, value)

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        value = GoveeAPI_GetCachedStateValue(self.hass, self._entry_id, self._device_cfg.get('device'), 'devices.capabilities.color_setting', 'colorTemperatureK')
        return value

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color."""
        value = GoveeAPI_GetCachedStateValue(self.hass, self._entry_id, self._device_cfg.get('device'), 'devices.capabilities.color_setting', 'colorRgb')
        return self._getRGBfromI(value)

    async def async_turn_on(self, **kwargs) -> None:
        """Async: Turn entity on"""
        try:
            _LOGGER.debug("%s - %s: async_turn_on", self._api_id, self._identifier)
            _LOGGER.debug("%s - %s: async_turn_on: kwargs = %s", self._api_id, self._identifier, kwargs)
            
            if ATTR_BRIGHTNESS in kwargs:
                state_capability = {
                    "type": "devices.capabilities.range",
                    "instance": 'brightness',
                    "value": math.ceil(brightness_to_value(self._brightness_scale, kwargs[ATTR_BRIGHTNESS]))   
                }
                if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
                    self.async_write_ha_state()

            if ATTR_COLOR_TEMP_KELVIN in kwargs:
                state_capability = {
                    "type": "devices.capabilities.color_setting",
                    "instance": 'colorTemperatureK',
                    "value": kwargs[ATTR_COLOR_TEMP_KELVIN]
                }
                if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
                    self.async_write_ha_state()

            if ATTR_RGB_COLOR in kwargs:
                state_capability = {
                    "type": "devices.capabilities.color_setting",
                    "instance": 'colorRgb',
                    "value": self._getIfromRGB(kwargs[ATTR_RGB_COLOR])
                }
                if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
                    self.async_write_ha_state()
            
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
        except Exception as e:
            _LOGGER.error("%s - %s: async_turn_off failed: %s (%s.%s)", self._api_id, self._identifier, str(e), e.__class__.__module__, type(e).__name__)
