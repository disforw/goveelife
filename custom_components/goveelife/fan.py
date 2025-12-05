"""Sensor entities for the Govee Life integration."""

import logging
import asyncio
import math

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.const import (
    STATE_ON,
    STATE_OFF,
    STATE_UNKNOWN,
)
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .entities import GoveeLifePlatformEntity
from .const import DOMAIN, CONF_COORDINATORS
from .utils import GoveeAPI_GetCachedStateValue, async_GoveeAPI_ControlDevice

_LOGGER = logging.getLogger(__name__)
PLATFORM = 'fan'
PLATFORM_DEVICE_TYPES = [
    'devices.types.air_purifier',
    'devices.types.fan'
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the fan platform."""
    _LOGGER.debug("Setting up %s platform entry: %s | %s", PLATFORM, DOMAIN, entry.entry_id)
    entities = []

    try:
        _LOGGER.debug("%s - async_setup_entry %s: Getting cloud devices from data store", entry.entry_id, PLATFORM)
        entry_data = hass.data[DOMAIN][entry.entry_id]
        api_devices = entry_data.get('devices', [])
    except Exception as e:
        _LOGGER.error("%s - async_setup_entry %s: Getting cloud devices from data store failed: %s (%s.%s)", entry.entry_id, PLATFORM, str(e), e.__class__.__module__, type(e).__name__)
        return False

    for device_cfg in api_devices:
        try:
            if device_cfg.get('type', STATE_UNKNOWN) not in PLATFORM_DEVICE_TYPES:
                continue

            device_id = device_cfg.get('device')
            _LOGGER.debug("%s - async_setup_entry %s: Setup device: %s", entry.entry_id, PLATFORM, device_id)
            coordinator = entry_data[CONF_COORDINATORS][device_id]
            entity = GoveeLifeFan(hass, entry, coordinator, device_cfg, platform=PLATFORM)
            entities.append(entity)
            await asyncio.sleep(0)
        except Exception as e:
            _LOGGER.error("%s - async_setup_entry %s: Setup device failed: %s (%s.%s)", entry.entry_id, PLATFORM, str(e), e.__class__.__module__, type(e).__name__)
            return False

    _LOGGER.info("%s - async_setup_entry: setup %s %s entities", entry.entry_id, len(entities), PLATFORM)
    if not entities:
        return None
    async_add_entities(entities)


class GoveeLifeFan(FanEntity, GoveeLifePlatformEntity):
    """Fan class for Govee Life integration."""

    _state_mapping = {}
    _state_mapping_set = {}
    _attr_preset_modes = []
    _attr_preset_modes_mapping = {}
    _attr_preset_modes_mapping_set = {}
    _speed_range = (1, 3)  # Default range, will be updated based on capabilities
    _speed_mapping = {}  # Maps modeValue to speed level (1-indexed)
    _speed_mapping_reverse = {}  # Maps speed level to modeValue
    _manual_work_mode = 1  # Default Manual workMode value
    _attr_supported_features = 0

    def _init_platform_specific(self, **kwargs) -> None:
        """Platform specific initialization actions."""
        _LOGGER.debug("%s - %s: _init_platform_specific", self._api_id, self._identifier)
        capabilities = self._device_cfg.get('capabilities', [])

        for cap in capabilities:
            if cap['type'] == 'devices.capabilities.on_off':
                # Added TURN_OFF so HA knows this entity supports turning off.
                self._attr_supported_features |= FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
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
                self._attr_supported_features |= FanEntityFeature.SET_SPEED
                
                manual_work_mode = None
                gear_modes = []
                
                for capFieldWork in cap['parameters']['fields']:
                    if capFieldWork['fieldName'] == 'workMode':
                        for workOption in capFieldWork.get('options', []):
                            self._attr_preset_modes_mapping[workOption['name']] = workOption['value']
                            # Track Manual mode workMode value (typically 1)
                            if workOption['name'].lower() in ['manual', 'gearmode']:
                                manual_work_mode = workOption['value']
                    elif capFieldWork['fieldName'] == 'modeValue':
                        for valueOption in capFieldWork.get('options', []):
                            if valueOption['name'] == 'gearMode':
                                # Store gear modes as speed levels instead of preset modes
                                for gearOption in valueOption.get('options', []):
                                    gear_modes.append({
                                        'name': gearOption['name'],
                                        'value': gearOption['value']
                                    })
                                if manual_work_mode is not None:
                                    # Add Manual preset
                                    self._attr_preset_modes.append('Manual')
                                    # Manual defaults to High (last gear mode)
                                    if gear_modes:
                                        self._attr_preset_modes_mapping_set['Manual'] = {
                                            "workMode": manual_work_mode, 
                                            "modeValue": gear_modes[-1]['value']
                                        }
                            elif valueOption['name'] != 'Custom':
                                # Add other modes like Sleep as presets
                                self._attr_preset_modes.append(valueOption['name'])
                                self._attr_preset_modes_mapping_set[valueOption['name']] = {
                                    "workMode": self._attr_preset_modes_mapping.get(valueOption['name'], valueOption.get('value', 0)), 
                                    "modeValue": valueOption.get('value', 0)
                                }
                
                # Map gear modes to speed levels
                if gear_modes:
                    num_speeds = len(gear_modes)
                    self._speed_range = (1, num_speeds)
                    # Store manual_work_mode for later use
                    self._manual_work_mode = manual_work_mode
                    # Create bidirectional mapping between speed level and modeValue
                    for idx, gear in enumerate(gear_modes):
                        speed_level = idx + 1  # 1-indexed speed levels
                        self._speed_mapping[gear['value']] = speed_level
                        self._speed_mapping_reverse[speed_level] = gear['value']
                    _LOGGER.debug("%s - %s: Speed range: %s, Speed mapping: %s", self._api_id, self._identifier, self._speed_range, self._speed_mapping)

    @property
    def state(self) -> str | None:
        """Return the current state of the entity."""
        value = GoveeAPI_GetCachedStateValue(self.hass, self._entry_id, self._device_cfg.get('device'), 'devices.capabilities.on_off', 'powerSwitch')
        return self._state_mapping.get(value, STATE_UNKNOWN)

    @property
    def is_on(self) -> bool:
        """Return true if entity is on."""
        return self.state == STATE_ON

    async def async_turn_on(self, speed: str = None, mode: str = None, **kwargs) -> None:
        """Async: Turn entity on."""
        try:
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
        except Exception as e:
            _LOGGER.error("%s - %s: async_turn_on failed: %s (%s.%s)", self._api_id, self._identifier, str(e), e.__class__.__module__, type(e).__name__)

    async def async_turn_off(self, **kwargs) -> None:
        """Async: Turn entity off."""
        try:
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
                _LOGGER.debug("%s - %s: async_turn_off: device already off", self._api_id, self._identifier)
        except Exception as e:
            _LOGGER.error("%s - %s: async_turn_off failed: %s (%s.%s)", self._api_id, self._identifier, str(e), e.__class__.__module__, type(e).__name__)

    @property
    def preset_mode(self) -> str | None:
        """Return the preset_mode of the entity."""
        value = GoveeAPI_GetCachedStateValue(self.hass, self._entry_id, self._device_cfg.get('device'), 'devices.capabilities.work_mode', 'workMode')
        if not value:
            return STATE_UNKNOWN
        
        work_mode = value.get('workMode')
        mode_value = value.get('modeValue')
        
        # Check if we're in manual mode (workMode == 1 or manual_work_mode)
        if work_mode == self._manual_work_mode:
            return 'Manual'
        
        # Otherwise, check for other preset modes (e.g., Sleep with workMode == 5)
        v = {"workMode": work_mode, "modeValue": mode_value}
        return next(
            (key for key, val in self._attr_preset_modes_mapping_set.items() if val == v),
            STATE_UNKNOWN,
        )

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if not self.is_on:
            return None
        
        value = GoveeAPI_GetCachedStateValue(self.hass, self._entry_id, self._device_cfg.get('device'), 'devices.capabilities.work_mode', 'workMode')
        if not value:
            return None
        
        work_mode = value.get('workMode')
        mode_value = value.get('modeValue')
        
        # Only return percentage if in manual mode
        if work_mode == self._manual_work_mode:
            # Get the speed level from modeValue
            speed_level = self._speed_mapping.get(mode_value)
            if speed_level is not None:
                # Convert speed level to percentage
                percentage = ranged_value_to_percentage(self._speed_range, speed_level)
                return percentage
        
        return None

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return self._speed_range[1]

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return
        
        # Convert percentage to speed level
        speed_level = math.ceil(percentage_to_ranged_value(self._speed_range, percentage))
        mode_value = self._speed_mapping_reverse.get(speed_level)
        
        if mode_value is None:
            _LOGGER.error("%s - %s: async_set_percentage: Could not find modeValue for speed level %s", self._api_id, self._identifier, speed_level)
            return
        
        # Set to manual mode with the specified speed
        state_capability = {
            "type": "devices.capabilities.work_mode",
            "instance": "workMode",
            "value": {
                "workMode": self._manual_work_mode,
                "modeValue": mode_value
            }
        }
        
        _LOGGER.debug("%s - %s: async_set_percentage: Setting speed to %s%% (level %s, modeValue %s)", 
                     self._api_id, self._identifier, percentage, speed_level, mode_value)
        
        if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
            if not self.is_on:
                # Turn on the device if it's off
                await self.async_turn_on()
            else:
                self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        state_capability = {
            "type": "devices.capabilities.work_mode",
            "instance": "workMode",
            "value": self._attr_preset_modes_mapping_set[preset_mode]
        }
        if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
            self.async_write_ha_state()
