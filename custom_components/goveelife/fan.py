"""Sensor entities for the Govee Life integration."""

import asyncio
import logging

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import CONF_COORDINATORS, DOMAIN
from .entities import GoveeLifePlatformEntity
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

    # Sleep mode percentage - half of Low speed (33% / 2 = 16%)
    # This ensures Sleep mode shows on the speed slider and doesn't appear as 'Off'
    SLEEP_MODE_PERCENTAGE = 16

    # Use 1% step to ensure slider display instead of buttons
    # This accommodates Sleep (16%), Low (33%), Medium (66%), and High (100%)
    _attr_percentage_step = 1.0

    _state_mapping = {}
    _state_mapping_set = {}
    _attr_preset_modes = []
    _attr_preset_modes_mapping = {}
    _attr_preset_modes_mapping_set = {}
    _ordered_named_fan_speeds = []  # Ordered list of speed names (e.g., ['Low', 'Medium', 'High'])
    _speed_mapping = {}  # Maps modeValue to speed name
    _speed_name_to_mode_value = {}  # Maps speed name to modeValue
    _manual_work_mode = 1  # Default Manual workMode value
    _sleep_work_mode = None  # Sleep mode workMode value (typically 5)
    _attr_supported_features = 0
    _device_sku = None  # Device SKU for model-specific handling

    # H7120-specific: workMode directly maps to speed/mode
    _h7120_work_mode_mapping = {
        1: ('Manual', 33),   # Low
        2: ('Manual', 66),   # Medium
        3: ('Manual', 100),  # High
        5: ('Sleep', 16)     # Sleep
    }

    # Reverse mapping for H7120: percentage to workMode
    _h7120_percentage_to_work_mode = {
        33: 1,   # Low
        66: 2,   # Medium
        100: 3,  # High
        16: 5    # Sleep
    }

    def _init_platform_specific(self, **kwargs) -> None:
        """Platform specific initialization actions."""
        _LOGGER.debug("%s - %s: _init_platform_specific", self._api_id, self._identifier)
        capabilities = self._device_cfg.get('capabilities', [])
        has_power_control = False

        # Get device SKU for model-specific handling
        self._device_sku = self._device_cfg.get('sku', None)
        _LOGGER.debug("%s - %s: Device SKU: %s", self._api_id, self._identifier, self._device_sku)

        for cap in capabilities:
            if cap['type'] == 'devices.capabilities.on_off':
                # Added TURN_OFF so HA knows this entity supports turning off.
                self._attr_supported_features |= FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
                has_power_control = True
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
                            # Common names for manual mode: 'Manual', 'gearMode'
                            if workOption['name'].lower() in ['manual', 'gearmode']:
                                manual_work_mode = workOption['value']
                                _LOGGER.debug("%s - %s: Found manual mode: %s = %s", self._api_id, self._identifier, workOption['name'], manual_work_mode)
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
                                    # Add Off preset only if device has power control
                                    if has_power_control:
                                        self._attr_preset_modes.append('Off')

                                    # Add Manual preset
                                    self._attr_preset_modes.append('Manual')
                                    # Manual defaults to High (last gear mode in the ordered list)
                                    # Note: Assumes gear_modes are ordered from low to high (e.g., Low, Medium, High)
                                    if gear_modes:
                                        self._attr_preset_modes_mapping_set['Manual'] = {
                                            "workMode": manual_work_mode,
                                            "modeValue": gear_modes[-1]['value']
                                        }
                                        _LOGGER.debug("%s - %s: Manual preset defaults to %s (modeValue %s)",
                                                     self._api_id, self._identifier, gear_modes[-1]['name'], gear_modes[-1]['value'])
                            elif valueOption['name'] != 'Custom':
                                # Add other modes like Sleep as presets
                                # The workMode value should come from the mapping we built earlier
                                work_mode_value = self._attr_preset_modes_mapping.get(valueOption['name'])
                                if work_mode_value is not None:
                                    self._attr_preset_modes.append(valueOption['name'])
                                    self._attr_preset_modes_mapping_set[valueOption['name']] = {
                                        "workMode": work_mode_value,
                                        "modeValue": valueOption.get('value', 0)
                                    }
                                    # Track Sleep mode workMode for percentage calculation
                                    if valueOption['name'].lower() == 'sleep':
                                        self._sleep_work_mode = work_mode_value
                                        _LOGGER.debug("%s - %s: Found sleep mode: workMode = %s", self._api_id, self._identifier, work_mode_value)
                                else:
                                    _LOGGER.warning("%s - %s: _init_platform_specific: Could not find workMode for %s", self._api_id, self._identifier, valueOption['name'])

                # Map gear modes to ordered list for percentage conversion
                if gear_modes:
                    # Store manual_work_mode for later use (only if found)
                    if manual_work_mode is not None:
                        self._manual_work_mode = manual_work_mode
                    # Create ordered list of speed names and mappings
                    for gear in gear_modes:
                        self._ordered_named_fan_speeds.append(gear['name'])
                        self._speed_mapping[gear['value']] = gear['name']
                        self._speed_name_to_mode_value[gear['name']] = gear['value']
                    _LOGGER.debug("%s - %s: Ordered fan speeds: %s", self._api_id, self._identifier, self._ordered_named_fan_speeds)
                    _LOGGER.debug("%s - %s: Speed mapping: %s", self._api_id, self._identifier, self._speed_mapping)

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
        # If device is off, return 'Off' preset
        if not self.is_on:
            return 'Off'

        value = GoveeAPI_GetCachedStateValue(self.hass, self._entry_id, self._device_cfg.get('device'), 'devices.capabilities.work_mode', 'workMode')
        if not value:
            _LOGGER.debug("%s - %s: preset_mode: No work_mode value from cache", self._api_id, self._identifier)
            return STATE_UNKNOWN

        # Handle case where value is not a dict
        if not isinstance(value, dict):
            _LOGGER.warning("%s - %s: preset_mode: Unexpected value type: %s, value: %s", self._api_id, self._identifier, type(value), value)
            return STATE_UNKNOWN

        work_mode = value.get('workMode')
        mode_value = value.get('modeValue')

        if work_mode is None:
            _LOGGER.warning("%s - %s: preset_mode: workMode is None in value: %s", self._api_id, self._identifier, value)
            return STATE_UNKNOWN

        # H7120-specific: workMode directly maps to preset/speed
        if self._device_sku == 'H7120':
            mapping = self._h7120_work_mode_mapping.get(work_mode)
            if mapping:
                preset, _ = mapping
                return preset
            _LOGGER.warning("%s - %s: preset_mode: Unknown workMode %s for H7120", self._api_id, self._identifier, work_mode)
            return STATE_UNKNOWN

        # Standard logic for other models
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
            _LOGGER.debug("%s - %s: percentage: No work_mode value from cache", self._api_id, self._identifier)
            return None

        # Handle case where value is not a dict
        if not isinstance(value, dict):
            _LOGGER.warning("%s - %s: percentage: Unexpected value type: %s, value: %s", self._api_id, self._identifier, type(value), value)
            return None

        work_mode = value.get('workMode')
        mode_value = value.get('modeValue')

        if work_mode is None:
            _LOGGER.warning("%s - %s: percentage: workMode is None in value: %s", self._api_id, self._identifier, value)
            return None

        # H7120-specific: workMode directly maps to percentage
        if self._device_sku == 'H7120':
            mapping = self._h7120_work_mode_mapping.get(work_mode)
            if mapping:
                _, percentage = mapping
                return percentage
            _LOGGER.warning("%s - %s: percentage: Unknown workMode %s for H7120", self._api_id, self._identifier, work_mode)
            return None

        # Standard logic for other models
        # Return percentage if in manual mode
        if work_mode == self._manual_work_mode:
            # Get the speed name from modeValue
            speed_name = self._speed_mapping.get(mode_value)
            if speed_name is not None and self._ordered_named_fan_speeds:
                # Convert speed name to percentage using ordered list
                return ordered_list_item_to_percentage(self._ordered_named_fan_speeds, speed_name)
            else:
                _LOGGER.debug("%s - %s: percentage: Could not map modeValue %s to speed name", self._api_id, self._identifier, mode_value)
        elif self._sleep_work_mode is not None and work_mode == self._sleep_work_mode:
            # Sleep mode shows a low percentage so slider doesn't show 'Off'
            # Using half of Low speed (33% / 2 = 16%)
            return self.SLEEP_MODE_PERCENTAGE

        return None

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return

        # H7120-specific: Commands use workMode=1 with modeValue for speeds
        if self._device_sku == 'H7120':
            # Turn on the device first if it's off
            if not self.is_on:
                _LOGGER.debug("%s - %s: async_set_percentage: Turning on device first", self._api_id, self._identifier)
                try:
                    await self.async_turn_on()
                    # Give the device a moment to turn on
                    await asyncio.sleep(0.5)
                except Exception as e:
                    _LOGGER.error("%s - %s: async_set_percentage: Failed to turn on device: %s (%s.%s)",
                                 self._api_id, self._identifier, str(e), e.__class__.__module__, type(e).__name__)
                    return

            # Map percentage to speed level (round to nearest)
            # 16% = Sleep (handled separately, shouldn't be called via percentage)
            # 33% = Low (modeValue 1) - nearest for 1-49%
            # 66% = Medium (modeValue 2) - nearest for 50-82%
            # 100% = High (modeValue 3) - nearest for 83-100%
            if percentage < 50:
                mode_value = 1  # Low
                speed_name = "Low"
            elif percentage < 83:
                mode_value = 2  # Medium
                speed_name = "Medium"
            else:
                mode_value = 3  # High
                speed_name = "High"

            # For H7120 commands: workMode=1 (Manual) with modeValue for speed
            state_capability = {
                "type": "devices.capabilities.work_mode",
                "instance": "workMode",
                "value": {
                    "workMode": 1,  # Manual mode
                    "modeValue": mode_value
                }
            }

            _LOGGER.debug("%s - %s: async_set_percentage (H7120): Setting speed to %s%% (%s, workMode=1, modeValue=%s)",
                         self._api_id, self._identifier, percentage, speed_name, mode_value)

            if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
                self.async_write_ha_state()
            return

        # Standard logic for other models
        if not self._ordered_named_fan_speeds:
            _LOGGER.error("%s - %s: async_set_percentage: No fan speeds configured", self._api_id, self._identifier)
            return

        # Turn on the device first if it's off
        if not self.is_on:
            _LOGGER.debug("%s - %s: async_set_percentage: Turning on device first", self._api_id, self._identifier)
            try:
                await self.async_turn_on()
                # Give the device a moment to turn on
                await asyncio.sleep(0.5)
            except Exception as e:
                _LOGGER.error("%s - %s: async_set_percentage: Failed to turn on device: %s (%s.%s)",
                             self._api_id, self._identifier, str(e), e.__class__.__module__, type(e).__name__)
                return

        # Convert percentage to speed name using ordered list
        speed_name = percentage_to_ordered_list_item(self._ordered_named_fan_speeds, percentage)
        mode_value = self._speed_name_to_mode_value.get(speed_name)

        if mode_value is None:
            _LOGGER.error("%s - %s: async_set_percentage: Could not find modeValue for speed %s", self._api_id, self._identifier, speed_name)
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

        _LOGGER.debug("%s - %s: async_set_percentage: Setting speed to %s%% (%s, modeValue %s)",
                     self._api_id, self._identifier, percentage, speed_name, mode_value)

        if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
            self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        # Handle 'Off' preset by turning off the device
        if preset_mode == 'Off':
            await self.async_turn_off()
            return

        # H7120-specific: Handle Sleep mode
        if self._device_sku == 'H7120' and preset_mode == 'Sleep':
            state_capability = {
                "type": "devices.capabilities.work_mode",
                "instance": "workMode",
                "value": {
                    "workMode": 5  # Sleep mode (no modeValue for Sleep)
                }
            }
            _LOGGER.debug("%s - %s: async_set_preset_mode (H7120): Setting to Sleep mode (workMode=5)", self._api_id, self._identifier)
            if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
                self.async_write_ha_state()
            return

        # H7120-specific: Handle Manual mode (defaults to High)
        if self._device_sku == 'H7120' and preset_mode == 'Manual':
            state_capability = {
                "type": "devices.capabilities.work_mode",
                "instance": "workMode",
                "value": {
                    "workMode": 1,  # Manual mode
                    "modeValue": 3  # High speed
                }
            }
            _LOGGER.debug("%s - %s: async_set_preset_mode (H7120): Setting to Manual/High mode (workMode=1, modeValue=3)", self._api_id, self._identifier)
            if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
                self.async_write_ha_state()
            return

        # Standard logic for other models
        state_capability = {
            "type": "devices.capabilities.work_mode",
            "instance": "workMode",
            "value": self._attr_preset_modes_mapping_set[preset_mode]
        }
        if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
            self.async_write_ha_state()
