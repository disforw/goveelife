"""Humidifier entities for the Govee Life integration."""

from __future__ import annotations

import logging
from typing import Final

from homeassistant.components.humidifier import (
    MODE_AUTO,
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICES,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

from .const import CONF_COORDINATORS, DOMAIN
from .entities import GoveeLifePlatformEntity
from .utils import GoveeAPI_GetCachedStateValue, async_GoveeAPI_ControlDevice

_LOGGER: Final = logging.getLogger(__name__)
platform = "humidifier"
platform_device_types = ["devices.types.humidifier", "devices.types.dehumidifier"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the humidifier platform."""
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
            if device_cfg.get("type", STATE_UNKNOWN) not in platform_device_types:
                continue
            device = device_cfg.get("device")
            _LOGGER.debug("%s - async_setup_entry %s: Setup device: %s", entry.entry_id, platform, device)
            coordinator = entry_data[CONF_COORDINATORS][device]
            entity = GoveeLifeHumidifier(hass, entry, coordinator, device_cfg, platform=platform)
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


class GoveeLifeHumidifier(HumidifierEntity, GoveeLifePlatformEntity):
    """Humidifier class for Govee Life integration."""

    def __init__(self, hass, entry, coordinator, device_cfg, **kwargs):
        """Initialize the humidifier entity."""
        self._state_mapping = {}
        self._state_mapping_set = {}
        self._attr_available_modes = []
        self._attr_preset_modes_mapping = {}
        self._attr_preset_modes_mapping_set = {}
        super().__init__(hass, entry, coordinator, device_cfg, **kwargs)

    def _init_platform_specific(self, **kwargs):
        """Platform specific initialization actions."""
        _LOGGER.debug("%s - %s: _init_platform_specific", self._api_id, self._identifier)
        self.device_class = self._device_cfg.get("type", [])
        if self.device_class == "devices.types.humidifier":
            self._attr_device_class = HumidifierDeviceClass.HUMIDIFIER
        elif self.device_class == "devices.types.dehumidifier":
            self._attr_device_class = HumidifierDeviceClass.DEHUMIDIFIER

        capabilities = self._device_cfg.get("capabilities", [])

        _LOGGER.debug(
            "%s - %s: _init_platform_specific: processing devices request capabilities",
            self._api_id,
            self._identifier,
        )
        for cap in capabilities:
            _LOGGER.debug("%s - %s: _init_platform_specific: processing cap: %s", self._api_id, self._identifier, cap)
            if cap["type"] == "devices.capabilities.on_off":
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
            elif cap["type"] == "devices.capabilities.work_mode":
                self._attr_supported_features |= HumidifierEntityFeature.MODES
                for capFieldWork in cap["parameters"]["fields"]:
                    if capFieldWork["fieldName"] == "workMode":
                        for workOption in capFieldWork.get("options", []):
                            self._attr_preset_modes_mapping[workOption["name"]] = workOption["value"]
                    elif capFieldWork["fieldName"] == "modeValue":
                        self._process_mode_value_options(capFieldWork.get("options", []))
            elif cap["type"] == "devices.capabilities.range" and cap["instance"] == "humidity":
                self._attr_min_humidity = cap["parameters"]["range"]["min"]
                self._attr_max_humidity = cap["parameters"]["range"]["max"]
            else:
                _LOGGER.debug(
                    "%s - %s: _init_platform_specific: cap unhandled: %s", self._api_id, self._identifier, cap
                )

    def _process_mode_value_options(self, options: list) -> None:
        """Parse modeValue options and populate available modes.

        Handles four modeValue option structures:
          1. Nested sub-options  — {"name": "gearMode", "options": [...]}
          2. Range-based         — {"name": "Auto", "range": {"min": 80, "max": 80}}
          3. Default-value       — {"name": "Dryer", "defaultValue": 0}
          4. Flat value          — {"name": "Normal", "value": 2}  (legacy)

        The modeValue option name always matches the corresponding workMode option
        name, so we can look up the workMode integer via _attr_preset_modes_mapping.
        """
        for valueOption in options:
            mode_name = valueOption.get("name", "")
            work_mode_value = self._attr_preset_modes_mapping.get(mode_name)

            if mode_name == "Custom":
                # Skip — Custom is a passthrough mode, not user-selectable
                continue
            elif "options" in valueOption:
                # Nested sub-options — expand each as an individual selectable mode.
                # Sub-option names may be absent (unnamed speeds); auto-generate.
                for gearOption in valueOption["options"]:
                    raw_name = gearOption.get("name")
                    gear_val = gearOption.get("value")
                    gear_name = raw_name if raw_name else f"{mode_name}: Speed {gear_val}"
                    if work_mode_value is not None and gear_val is not None:
                        self._attr_available_modes.append(gear_name)
                        self._attr_preset_modes_mapping_set[gear_name] = {
                            "workMode": work_mode_value,
                            "modeValue": gear_val,
                        }
                        _LOGGER.debug(
                            "%s - %s: Adding sub-mode %s: %s",
                            self._api_id,
                            self._identifier,
                            gear_name,
                            self._attr_preset_modes_mapping_set[gear_name],
                        )
                    else:
                        _LOGGER.warning(
                            "%s - %s: Could not map sub-mode %s (work_mode=%s, val=%s)",
                            self._api_id,
                            self._identifier,
                            gear_name,
                            work_mode_value,
                            gear_val,
                        )
            elif "range" in valueOption:
                # Range-based mode — use the minimum value as the representative modeValue
                range_val = valueOption["range"].get("min", 0)
                if work_mode_value is not None:
                    self._attr_available_modes.append(mode_name)
                    self._attr_preset_modes_mapping_set[mode_name] = {
                        "workMode": work_mode_value,
                        "modeValue": range_val,
                    }
                    _LOGGER.debug(
                        "%s - %s: Adding range mode %s: workMode=%s, modeValue=%s",
                        self._api_id,
                        self._identifier,
                        mode_name,
                        work_mode_value,
                        range_val,
                    )
            elif "defaultValue" in valueOption:
                # Default-value mode
                default_val = valueOption["defaultValue"]
                if work_mode_value is not None:
                    self._attr_available_modes.append(mode_name)
                    self._attr_preset_modes_mapping_set[mode_name] = {
                        "workMode": work_mode_value,
                        "modeValue": default_val,
                    }
                    _LOGGER.debug(
                        "%s - %s: Adding default mode %s: workMode=%s, modeValue=%s",
                        self._api_id,
                        self._identifier,
                        mode_name,
                        work_mode_value,
                        default_val,
                    )
            elif "value" in valueOption:
                # Flat value mode (legacy structure — name + explicit integer value)
                if work_mode_value is not None:
                    self._attr_available_modes.append(mode_name)
                    self._attr_preset_modes_mapping_set[mode_name] = {
                        "workMode": work_mode_value,
                        "modeValue": valueOption["value"],
                    }
                    _LOGGER.debug(
                        "%s - %s: Adding flat mode %s: workMode=%s, modeValue=%s",
                        self._api_id,
                        self._identifier,
                        mode_name,
                        work_mode_value,
                        valueOption["value"],
                    )
            else:
                _LOGGER.warning(
                    "%s - %s: unrecognised modeValue structure for %s: %s",
                    self._api_id,
                    self._identifier,
                    mode_name,
                    valueOption,
                )

    @property
    def current_humidity(self) -> float | None:
        """Return current humidity."""
        value = GoveeAPI_GetCachedStateValue(
            self.hass,
            self._entry_id,
            self._device_cfg.get("device"),
            "devices.capabilities.property",
            "sensorHumidity",
        )
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            _LOGGER.warning(
                "%s - %s: current_humidity: could not convert value to float: %s",
                self._api_id,
                self._identifier,
                value,
            )
            return None

    @property
    def is_on(self) -> bool:
        """Return true if entity is on."""
        value = GoveeAPI_GetCachedStateValue(
            self.hass,
            self._entry_id,
            self._device_cfg.get("device"),
            "devices.capabilities.on_off",
            "powerSwitch",
        )
        return self._state_mapping.get(value) == STATE_ON

    @property
    def mode(self) -> str | None:
        """Return the current mode, derived from the cached workMode state."""
        value = GoveeAPI_GetCachedStateValue(
            self.hass,
            self._entry_id,
            self._device_cfg.get("device"),
            "devices.capabilities.work_mode",
            "workMode",
        )
        if not isinstance(value, dict) or value.get("workMode") is None:
            return None if self._attr_available_modes else MODE_AUTO
        current = {"workMode": value.get("workMode"), "modeValue": value.get("modeValue")}
        for name, mapping in self._attr_preset_modes_mapping_set.items():
            if mapping == current:
                return name
        # modeValue may be a live setpoint (range modes) - fall back to matching workMode only,
        # but only when that is unambiguous (several presets can share one workMode)
        candidates = [
            name
            for name, mapping in self._attr_preset_modes_mapping_set.items()
            if mapping.get("workMode") == current["workMode"]
        ]
        return candidates[0] if len(candidates) == 1 else None

    @property
    def target_humidity(self) -> float | None:
        """Return the target humidity from the humidity range capability, if present."""
        if getattr(self, "_attr_min_humidity", None) is None:
            return None
        value = GoveeAPI_GetCachedStateValue(
            self.hass,
            self._entry_id,
            self._device_cfg.get("device"),
            "devices.capabilities.range",
            "humidity",
        )
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    async def async_turn_on(self, speed: str = None, mode: str = None, **kwargs) -> None:
        """Async: Turn entity on"""
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
        """Async: Turn entity off"""
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
                _LOGGER.debug("%s - %s: async_turn_on: device already off", self._api_id, self._identifier)
        except Exception as e:
            _LOGGER.error(
                "%s - %s: async_turn_off failed: %s (%s.%s)",
                self._api_id,
                self._identifier,
                str(e),
                e.__class__.__module__,
                type(e).__name__,
            )

    async def async_set_mode(self, mode: str | None = None, **kwargs) -> None:
        """Set new target preset mode."""
        preset_mode = mode or kwargs.get("preset_mode")
        if preset_mode is None:
            _LOGGER.warning(
                "%s - %s: async_set_mode called with no mode kwarg: %s", self._api_id, self._identifier, kwargs
            )
            return
        if preset_mode not in self._attr_preset_modes_mapping_set:
            _LOGGER.warning(
                "%s - %s: async_set_mode: unknown mode %s (available: %s)",
                self._api_id,
                self._identifier,
                preset_mode,
                self._attr_available_modes,
            )
            return
        state_capability = {
            "type": "devices.capabilities.work_mode",
            "instance": "workMode",
            "value": self._attr_preset_modes_mapping_set[preset_mode],
        }
        if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
            self.async_write_ha_state()

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        state_capability = {
            "type": "devices.capabilities.range",
            "instance": "humidity",
            "value": humidity,
        }
        if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
            self.async_write_ha_state()
