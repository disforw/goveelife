"""Fan entities for the Govee Life integration."""

import asyncio
import logging

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICES,
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
PLATFORM = "fan"
PLATFORM_DEVICE_TYPES = ["devices.types.air_purifier", "devices.types.fan"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the fan platform."""
    _LOGGER.debug("Setting up %s platform entry: %s | %s", PLATFORM, DOMAIN, entry.entry_id)
    entities = []

    try:
        _LOGGER.debug("%s - async_setup_entry %s: Getting cloud devices from data store", entry.entry_id, PLATFORM)
        entry_data = hass.data[DOMAIN][entry.entry_id]
        api_devices = entry_data.get(CONF_DEVICES, [])
    except Exception as e:
        _LOGGER.error(
            "%s - async_setup_entry %s: Getting cloud devices from data store failed: %s (%s.%s)",
            entry.entry_id,
            PLATFORM,
            str(e),
            e.__class__.__module__,
            type(e).__name__,
        )
        return False

    for device_cfg in api_devices:
        try:
            if device_cfg.get("type", STATE_UNKNOWN) not in PLATFORM_DEVICE_TYPES:
                continue

            device_id = device_cfg.get("device")
            _LOGGER.debug("%s - async_setup_entry %s: Setup device: %s", entry.entry_id, PLATFORM, device_id)
            coordinator = entry_data[CONF_COORDINATORS][device_id]
            entity = GoveeLifeFan(hass, entry, coordinator, device_cfg, platform=PLATFORM)
            entities.append(entity)
        except Exception as e:
            _LOGGER.error(
                "%s - async_setup_entry %s: Setup device failed: %s (%s.%s)",
                entry.entry_id,
                PLATFORM,
                str(e),
                e.__class__.__module__,
                type(e).__name__,
            )
            return False

    _LOGGER.info("%s - async_setup_entry: setup %s %s entities", entry.entry_id, len(entities), PLATFORM)
    if not entities:
        return None
    async_add_entities(entities)


class GoveeLifeFan(FanEntity, GoveeLifePlatformEntity):
    """Fan class for Govee Life integration."""

    # Sleep mode percentage - half of Low speed (33% / 2 = 16%)
    SLEEP_MODE_PERCENTAGE = 16

    # Use 1% step to ensure slider display instead of buttons
    _attr_percentage_step = 1.0

    def __init__(self, hass, entry, coordinator, device_cfg, **kwargs):
        """Initialize the fan entity."""
        # Instance-level mutable defaults
        self._state_mapping = {}
        self._state_mapping_set = {}
        self._ordered_named_fan_speeds = []
        self._speed_mapping = {}
        self._speed_name_to_mode_value = {}
        self._manual_work_mode = 1
        self._sleep_work_mode = None
        self._flat_work_mode = False
        self._attr_supported_features = 0
        self._support_oscillation = False
        super().__init__(hass, entry, coordinator, device_cfg, **kwargs)

    def _init_platform_specific(self, **kwargs) -> None:
        """Platform specific initialization actions."""
        _LOGGER.debug("%s - %s: _init_platform_specific", self._api_id, self._identifier)
        capabilities = self._device_cfg.get("capabilities", [])
        has_power_control = False

        # Set per device so duplication of modes does not occur after each HA restart
        self._attr_preset_modes = []
        self._attr_preset_modes_mapping = {}
        self._attr_preset_modes_mapping_set = {}

        # --- First pass: collect work_mode data so we can detect flat-workMode devices ---
        work_mode_options = []  # list of {name, value} from workMode field
        gear_modes = []  # list of {name, value} from gearMode modeValue sub-options
        any_named_modevalue = False  # True if any modeValue option carries sub-options with names
        manual_work_mode = None
        work_mode_cap = None

        for cap in capabilities:
            if cap["type"] == "devices.capabilities.work_mode":
                work_mode_cap = cap
                for capFieldWork in cap["parameters"]["fields"]:
                    if capFieldWork["fieldName"] == "workMode":
                        for workOption in capFieldWork.get("options", []):
                            work_mode_options.append({"name": workOption["name"], "value": workOption["value"]})
                            if workOption["name"].lower() in ["manual", "gearmode"]:
                                manual_work_mode = workOption["value"]
                    elif capFieldWork["fieldName"] == "modeValue":
                        for valueOption in capFieldWork.get("options", []):
                            if valueOption["name"] == "gearMode":
                                for gearOption in valueOption.get("options", []):
                                    # Fix 1 & 2: auto-generate name when absent
                                    gear_name = gearOption.get("name") or f"Speed {gearOption['value']}"
                                    gear_modes.append({"name": gear_name, "value": gearOption["value"]})
                            elif valueOption.get("options"):
                                # Another manual-mode sub-option block with options
                                sub_has_names = any(o.get("name") for o in valueOption["options"])
                                if sub_has_names:
                                    any_named_modevalue = True
                                for subOpt in valueOption["options"]:
                                    sub_name = subOpt.get("name") or f"Speed {subOpt['value']}"
                                    gear_modes.append({"name": sub_name, "value": subOpt["value"]})

        # --- Fix 3: detect "flat workMode" devices ---
        # A flat-workMode device has workMode options but NO gearMode sub-options AND
        # NO named modeValue sub-options with gear levels. In this case every workMode
        # option IS a distinct speed/preset level (e.g. H7120: Low=1, Medium=2, High=3, Sleep=5).
        flat_work_mode = bool(work_mode_options) and not gear_modes and not any_named_modevalue

        if flat_work_mode:
            self._flat_work_mode = True
            _LOGGER.debug(
                "%s - %s: Detected flat-workMode device — treating workMode options as speed levels",
                self._api_id,
                self._identifier,
            )
            # Treat each workMode option as a speed entry
            for opt in work_mode_options:
                gear_modes.append({"name": opt["name"], "value": opt["value"]})
            # No nested manual_work_mode — the workMode value itself IS the speed
            # We set manual_work_mode to a sentinel so the standard percentage logic uses
            # the workMode value directly (we'll store the workMode in _speed_mapping keyed
            # by workMode value, and in async_set_percentage we send workMode=<value>).
            manual_work_mode = None  # handled generically via _speed_mapping below

        # --- Second pass: process on_off and toggle capabilities ---
        for cap in capabilities:
            if cap["type"] == "devices.capabilities.on_off":
                self._attr_supported_features |= FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
                has_power_control = True
                for option in cap["parameters"]["options"]:
                    if option["name"] == "on":
                        self._state_mapping[option["value"]] = STATE_ON
                        self._state_mapping_set[STATE_ON] = option["value"]
                    elif option["name"] == "off":
                        self._state_mapping[option["value"]] = STATE_OFF
                        self._state_mapping_set[STATE_OFF] = option["value"]
                    else:
                        _LOGGER.warning(
                            "%s - %s: _init_platform_specific: unhandled cap option: %s -> %s",
                            self._api_id,
                            self._identifier,
                            cap["type"],
                            option,
                        )

            # Fix 4: expose oscillationToggle
            elif cap["type"] == "devices.capabilities.toggle" and cap.get("instance") == "oscillationToggle":
                self._support_oscillation = True
                self._attr_supported_features |= FanEntityFeature.OSCILLATE
                _LOGGER.debug("%s - %s: Oscillation supported", self._api_id, self._identifier)

        # --- Third pass: build preset modes and speed mappings from work_mode cap ---
        if work_mode_cap is not None:
            self._attr_supported_features |= FanEntityFeature.PRESET_MODE
            self._attr_supported_features |= FanEntityFeature.SET_SPEED

            # Populate preset_modes_mapping from workMode field options
            for opt in work_mode_options:
                self._attr_preset_modes_mapping[opt["name"]] = opt["value"]

            if flat_work_mode:
                # Each workMode option is a speed level; map them all
                if has_power_control:
                    self._attr_preset_modes.append("Off")
                for opt in work_mode_options:
                    self._attr_preset_modes.append(opt["name"])
                    self._attr_preset_modes_mapping_set[opt["name"]] = {
                        "workMode": opt["value"],
                        "modeValue": 0,
                    }
                    # Track sleep mode
                    if opt["name"].lower() == "sleep":
                        self._sleep_work_mode = opt["value"]
                # Speed list mirrors workMode options (used for percentage calculation)
                for opt in work_mode_options:
                    self._ordered_named_fan_speeds.append(opt["name"])
                    self._speed_mapping[opt["value"]] = opt["name"]
                    self._speed_name_to_mode_value[opt["name"]] = opt["value"]
                # For flat-workMode, _manual_work_mode is unused (we look up by speed name)
            else:
                # Standard nested gearMode / modeValue structure
                for capFieldWork in work_mode_cap["parameters"]["fields"]:
                    if capFieldWork["fieldName"] == "modeValue":
                        for valueOption in capFieldWork.get("options", []):
                            if valueOption["name"] == "gearMode":
                                if manual_work_mode is not None:
                                    if has_power_control:
                                        self._attr_preset_modes.append("Off")
                                    self._attr_preset_modes.append("Manual")
                                    if gear_modes:
                                        self._attr_preset_modes_mapping_set["Manual"] = {
                                            "workMode": manual_work_mode,
                                            "modeValue": gear_modes[-1]["value"],
                                        }
                                        _LOGGER.debug(
                                            "%s - %s: Manual preset defaults to %s (modeValue %s)",
                                            self._api_id,
                                            self._identifier,
                                            gear_modes[-1]["name"],
                                            gear_modes[-1]["value"],
                                        )
                            elif valueOption["name"] != "Custom" and valueOption["name"] != "gearMode":
                                # Other modes like Sleep, Auto, etc.
                                work_mode_value = self._attr_preset_modes_mapping.get(valueOption["name"])
                                if work_mode_value is not None:
                                    self._attr_preset_modes.append(valueOption["name"])
                                    self._attr_preset_modes_mapping_set[valueOption["name"]] = {
                                        "workMode": work_mode_value,
                                        "modeValue": valueOption.get("value", 0),
                                    }
                                    if valueOption["name"].lower() == "sleep":
                                        self._sleep_work_mode = work_mode_value
                                        _LOGGER.debug(
                                            "%s - %s: Found sleep mode: workMode = %s",
                                            self._api_id,
                                            self._identifier,
                                            work_mode_value,
                                        )
                                else:
                                    _LOGGER.warning(
                                        "%s - %s: _init_platform_specific: Could not find workMode for %s",
                                        self._api_id,
                                        self._identifier,
                                        valueOption["name"],
                                    )

                # Map gear modes to ordered list for percentage conversion
                if gear_modes:
                    if manual_work_mode is not None:
                        self._manual_work_mode = manual_work_mode
                    for gear in gear_modes:
                        self._ordered_named_fan_speeds.append(gear["name"])
                        self._speed_mapping[gear["value"]] = gear["name"]
                        self._speed_name_to_mode_value[gear["name"]] = gear["value"]
                    _LOGGER.debug(
                        "%s - %s: Ordered fan speeds: %s",
                        self._api_id,
                        self._identifier,
                        self._ordered_named_fan_speeds,
                    )
                    _LOGGER.debug("%s - %s: Speed mapping: %s", self._api_id, self._identifier, self._speed_mapping)

    @property
    def state(self) -> str | None:
        """Return the current state of the entity."""
        value = GoveeAPI_GetCachedStateValue(
            self.hass, self._entry_id, self._device_cfg.get("device"), "devices.capabilities.on_off", "powerSwitch"
        )
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
                    "instance": "powerSwitch",
                    "value": self._state_mapping_set[STATE_ON],
                }
                if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
                    self.async_write_ha_state()
            else:
                _LOGGER.debug("%s - %s: async_turn_on: device already on", self._api_id, self._identifier)
        except Exception as e:
            _LOGGER.error(
                "%s - %s: async_turn_on failed: %s (%s.%s)",
                self._api_id,
                self._identifier,
                str(e),
                e.__class__.__module__,
                type(e).__name__,
            )

    async def async_turn_off(self, **kwargs) -> None:
        """Async: Turn entity off."""
        try:
            _LOGGER.debug("%s - %s: async_turn_off: kwargs = %s", self._api_id, self._identifier, kwargs)
            if self.is_on:
                state_capability = {
                    "type": "devices.capabilities.on_off",
                    "instance": "powerSwitch",
                    "value": self._state_mapping_set[STATE_OFF],
                }
                if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
                    self.async_write_ha_state()
            else:
                _LOGGER.debug("%s - %s: async_turn_off: device already off", self._api_id, self._identifier)
        except Exception as e:
            _LOGGER.error(
                "%s - %s: async_turn_off failed: %s (%s.%s)",
                self._api_id,
                self._identifier,
                str(e),
                e.__class__.__module__,
                type(e).__name__,
            )

    @property
    def preset_mode(self) -> str | None:
        """Return the preset_mode of the entity."""
        if not self.is_on:
            return "Off"

        value = GoveeAPI_GetCachedStateValue(
            self.hass, self._entry_id, self._device_cfg.get("device"), "devices.capabilities.work_mode", "workMode"
        )
        if not value:
            _LOGGER.debug("%s - %s: preset_mode: No work_mode value from cache", self._api_id, self._identifier)
            return STATE_UNKNOWN

        if not isinstance(value, dict):
            _LOGGER.warning(
                "%s - %s: preset_mode: Unexpected value type: %s, value: %s",
                self._api_id,
                self._identifier,
                type(value),
                value,
            )
            return STATE_UNKNOWN

        work_mode = value.get("workMode")
        mode_value = value.get("modeValue")

        if work_mode is None:
            _LOGGER.warning(
                "%s - %s: preset_mode: workMode is None in value: %s", self._api_id, self._identifier, value
            )
            return STATE_UNKNOWN

        # For flat-workMode devices the workMode value IS the speed/preset name
        if self._flat_work_mode:
            speed_name = self._speed_mapping.get(work_mode)
            if speed_name:
                return speed_name
            return STATE_UNKNOWN

        # Standard nested structure
        if work_mode == self._manual_work_mode:
            return "Manual"

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

        value = GoveeAPI_GetCachedStateValue(
            self.hass, self._entry_id, self._device_cfg.get("device"), "devices.capabilities.work_mode", "workMode"
        )
        if not value:
            _LOGGER.debug("%s - %s: percentage: No work_mode value from cache", self._api_id, self._identifier)
            return None

        if not isinstance(value, dict):
            _LOGGER.warning(
                "%s - %s: percentage: Unexpected value type: %s, value: %s",
                self._api_id,
                self._identifier,
                type(value),
                value,
            )
            return None

        work_mode = value.get("workMode")
        mode_value = value.get("modeValue")

        if work_mode is None:
            _LOGGER.warning("%s - %s: percentage: workMode is None in value: %s", self._api_id, self._identifier, value)
            return None

        # For flat-workMode devices the workMode value maps directly to a speed name
        if self._flat_work_mode:
            speed_name = self._speed_mapping.get(work_mode)
            if speed_name and self._ordered_named_fan_speeds:
                return ordered_list_item_to_percentage(self._ordered_named_fan_speeds, speed_name)
            return None

        # Standard nested structure
        if work_mode == self._manual_work_mode:
            speed_name = self._speed_mapping.get(mode_value)
            if speed_name is not None and self._ordered_named_fan_speeds:
                return ordered_list_item_to_percentage(self._ordered_named_fan_speeds, speed_name)
            else:
                _LOGGER.debug(
                    "%s - %s: percentage: Could not map modeValue %s to speed name",
                    self._api_id,
                    self._identifier,
                    mode_value,
                )
        elif self._sleep_work_mode is not None and work_mode == self._sleep_work_mode:
            return self.SLEEP_MODE_PERCENTAGE

        return None

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return

        if not self._ordered_named_fan_speeds:
            _LOGGER.error("%s - %s: async_set_percentage: No fan speeds configured", self._api_id, self._identifier)
            return

        if not self.is_on:
            _LOGGER.debug("%s - %s: async_set_percentage: Turning on device first", self._api_id, self._identifier)
            try:
                await self.async_turn_on()
                await asyncio.sleep(0.5)
            except Exception as e:
                _LOGGER.error(
                    "%s - %s: async_set_percentage: Failed to turn on device: %s (%s.%s)",
                    self._api_id,
                    self._identifier,
                    str(e),
                    e.__class__.__module__,
                    type(e).__name__,
                )
                return

        speed_name = percentage_to_ordered_list_item(self._ordered_named_fan_speeds, percentage)
        mode_value = self._speed_name_to_mode_value.get(speed_name)

        if mode_value is None:
            _LOGGER.error(
                "%s - %s: async_set_percentage: Could not find modeValue for speed %s",
                self._api_id,
                self._identifier,
                speed_name,
            )
            return

        # For flat-workMode devices mode_value IS the workMode; no nested modeValue needed
        if self._flat_work_mode:
            state_capability = {
                "type": "devices.capabilities.work_mode",
                "instance": "workMode",
                "value": {"workMode": mode_value, "modeValue": 0},
            }
        else:
            state_capability = {
                "type": "devices.capabilities.work_mode",
                "instance": "workMode",
                "value": {"workMode": self._manual_work_mode, "modeValue": mode_value},
            }

        _LOGGER.debug(
            "%s - %s: async_set_percentage: Setting speed to %s%% (%s, capability %s)",
            self._api_id,
            self._identifier,
            percentage,
            speed_name,
            state_capability["value"],
        )

        if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
            self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        if preset_mode == "Off":
            await self.async_turn_off()
            return

        if preset_mode not in self._attr_preset_modes_mapping_set:
            _LOGGER.warning(
                "%s - %s: async_set_preset_mode: Unknown preset mode %s",
                self._api_id,
                self._identifier,
                preset_mode,
            )
            return

        state_capability = {
            "type": "devices.capabilities.work_mode",
            "instance": "workMode",
            "value": self._attr_preset_modes_mapping_set[preset_mode],
        }
        _LOGGER.debug(
            "%s - %s: async_set_preset_mode: Setting preset to %s (%s)",
            self._api_id,
            self._identifier,
            preset_mode,
            state_capability["value"],
        )
        if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
            self.async_write_ha_state()

    # --- Fix 4: Oscillation support ---

    @property
    def oscillating(self) -> bool | None:
        """Return whether the fan is oscillating."""
        if not self._support_oscillation:
            return None
        value = GoveeAPI_GetCachedStateValue(
            self.hass,
            self._entry_id,
            self._device_cfg.get("device"),
            "devices.capabilities.toggle",
            "oscillationToggle",
        )
        return value == 1

    async def async_oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""
        cap = {
            "type": "devices.capabilities.toggle",
            "instance": "oscillationToggle",
            "value": 1 if oscillating else 0,
        }
        if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, cap):
            self.async_write_ha_state()
