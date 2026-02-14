"""Light entities for the Govee Life integration."""

from __future__ import annotations

import asyncio
import logging
import math
from typing import Final

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICES,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util.color import brightness_to_value, value_to_brightness

from .const import CONF_COORDINATORS, DOMAIN
from .entities import GoveeLifePlatformEntity
from .utils import (
    GoveeAPI_GetCachedStateValue,
    async_GoveeAPI_ControlDevice,
    async_GoveeAPI_GetDynamicDIYScenes,
    async_GoveeAPI_GetDynamicScenes,
)

_LOGGER: Final = logging.getLogger(__name__)
platform = "light"
platform_device_types = ["devices.types.light"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up the light platform."""
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
            d = device_cfg.get("device")
            _LOGGER.debug("%s - async_setup_entry %s: Setup device: %s", entry.entry_id, platform, d)
            coordinator = entry_data[CONF_COORDINATORS][d]
            entity = GoveeLifeLight(hass, entry, coordinator, device_cfg, platform=platform)
            entities.append(entity)
            await asyncio.sleep(0)
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


class GoveeLifeLight(LightEntity, GoveeLifePlatformEntity, RestoreEntity):
    """Light class for Govee Life integration."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, coordinator, device_cfg, **kwargs):
        """Initialize a Govee Life light."""
        super().__init__(hass, entry, coordinator, device_cfg, **kwargs)
        self._platform_specific_init()

    def _platform_specific_init(self):
        """Initialize light specific variables and parameters."""
        self._state_mapping = {}
        self._state_mapping_set = {}
        self._state_mapping[1] = STATE_ON
        self._state_mapping[0] = STATE_OFF
        self._state_mapping_set[STATE_ON] = 1
        self._state_mapping_set[STATE_OFF] = 0
        self._temperature_scale = None
        self._brightness_scale = None
        self._support_brightness = None
        self._support_color = None
        self._support_color_temp = None
        self._support_scenes = False
        self._has_dynamic_scenes = False
        self._available_scenes = []
        self._current_scene = None
        self._dynamic_scenes = []
        self._scene_value_map = {}
        self._diy_scenes = []

        _LOGGER.info("%s - %s: Device capabilities:", self._api_id, self._identifier)
        for cap in self._device_cfg.get("capabilities", []):
            _LOGGER.info(
                "%s - %s: - Capability: type=%s, instance=%s",
                self._api_id,
                self._identifier,
                cap.get("type"),
                cap.get("instance"),
            )

        try:
            for cap in self._device_cfg.get("capabilities", []):
                if cap["type"] == "devices.capabilities.range":
                    if cap["instance"] == "brightness":
                        self._support_brightness = True
                        self._brightness_scale = (
                            cap.get("parameters", {}).get("range", {}).get("min", 1),
                            cap.get("parameters", {}).get("range", {}).get("max", 100),
                        )
                        _LOGGER.info("%s - %s: Brightness support enabled", self._api_id, self._identifier)

                elif cap["type"] == "devices.capabilities.color_setting":
                    if cap["instance"] == "colorRgb":
                        self._support_color = True
                        _LOGGER.info("%s - %s: RGB color support enabled", self._api_id, self._identifier)
                    elif cap["instance"] == "colorTemperatureK":
                        self._support_color_temp = True
                        self._temperature_scale = (
                            cap.get("parameters", {}).get("range", {}).get("min", 2000),
                            cap.get("parameters", {}).get("range", {}).get("max", 9000),
                        )
                        _LOGGER.info("%s - %s: Color temperature support enabled", self._api_id, self._identifier)

                elif cap["type"] == "devices.capabilities.dynamic_scene":
                    _LOGGER.info(
                        "%s - %s: Found dynamic_scene capability with instance: %s",
                        self._api_id,
                        self._identifier,
                        cap.get("instance"),
                    )
                    if cap["instance"] == "lightScene":
                        self._support_scenes = True
                        self._has_dynamic_scenes = True
                        static_scenes = cap.get("parameters", {}).get("options", [])
                        _LOGGER.info(
                            "%s - %s: Found %d static scenes in capabilities",
                            self._api_id,
                            self._identifier,
                            len(static_scenes),
                        )

                        for scene in static_scenes:
                            scene_name = scene.get("name")
                            scene_value = scene.get("value")
                            _LOGGER.debug(
                                "%s - %s: Static scene: %s = %s",
                                self._api_id,
                                self._identifier,
                                scene_name,
                                scene_value,
                            )
                            if scene_name and scene_value is not None:
                                self._available_scenes.append(scene_name)
                                self._scene_value_map[scene_name] = scene_value

                        _LOGGER.info(
                            "%s - %s: Scene support enabled with %d scenes: %s",
                            self._api_id,
                            self._identifier,
                            len(self._available_scenes),
                            self._available_scenes,
                        )

                elif cap["type"] == "devices.capabilities.music_setting":
                    _LOGGER.debug("%s - %s: Found music_setting capability", self._api_id, self._identifier)
                    pass  # TO-BE-DONE: implement as select entity type
                elif cap["type"] == "devices.capabilities.dynamic_setting":
                    _LOGGER.debug("%s - %s: Found dynamic_setting capability", self._api_id, self._identifier)
                    pass  # TO-BE-DONE: implement as select ? unsure about setting effect
                else:
                    _LOGGER.debug(
                        "%s - %s: _init_platform_specific: cap unhandled: %s", self._api_id, self._identifier, cap
                    )

            _LOGGER.info(
                "%s - %s: Final state - scenes=%s (%d scenes), brightness=%s, color=%s, color_temp=%s",
                self._api_id,
                self._identifier,
                self._support_scenes,
                len(self._available_scenes),
                self._support_brightness,
                self._support_color,
                self._support_color_temp,
            )

        except Exception as e:
            _LOGGER.error(
                "%s - %s: _platform_specific_init failed: %s (%s.%s)",
                self._api_id,
                self._identifier,
                str(e),
                e.__class__.__module__,
                type(e).__name__,
            )

    def _getRGBfromI(self, RGBint):
        if RGBint is None:
            return None
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
    def supported_features(self) -> LightEntityFeature:
        """Flag supported features."""
        if self._support_scenes or self._has_dynamic_scenes:
            return LightEntityFeature.EFFECT
        return LightEntityFeature(0)

    @property
    def supported_color_modes(self) -> set[ColorMode] | set[str] | None:
        """Flag supported color modes."""
        color_modes = set()

        if self._support_color and self._support_color_temp:
            color_modes.add(ColorMode.RGB)
            color_modes.add(ColorMode.COLOR_TEMP)
        elif self._support_color:
            color_modes.add(ColorMode.RGB)
        elif self._support_color_temp:
            color_modes.add(ColorMode.COLOR_TEMP)
        elif self._support_brightness:
            color_modes.add(ColorMode.BRIGHTNESS)
        else:
            color_modes.add(ColorMode.ONOFF)

        _LOGGER.debug("%s - %s: Supported color modes: %s", self._api_id, self._identifier, color_modes)
        return color_modes

    @property
    def color_mode(self) -> ColorMode | str | None:
        """Return the color mode of the light."""
        if self._support_color_temp and self.color_temp_kelvin is not None:
            return ColorMode.COLOR_TEMP
        elif self._support_color:
            return ColorMode.RGB
        elif self._support_brightness:
            return ColorMode.BRIGHTNESS
        else:
            return ColorMode.ONOFF

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        if not self._support_scenes:
            _LOGGER.debug("%s - %s: effect_list - no scene support", self._api_id, self._identifier)
            return None

        all_scenes = []
        for scene in self._diy_scenes:
            display_name = scene.get("_display_name")
            if display_name and display_name not in all_scenes:
                all_scenes.append(display_name)

        for name in self._available_scenes:
            if name not in all_scenes:
                all_scenes.append(name)
        for scene in self._dynamic_scenes:
            scene_name = scene.get("name")
            if scene_name and scene_name not in all_scenes:
                all_scenes.append(scene_name)

        _LOGGER.debug(
            "%s - %s: effect_list returning %d effects: %s",
            self._api_id,
            self._identifier,
            len(all_scenes),
            all_scenes[:5],
        )

        return all_scenes if all_scenes else None

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        _LOGGER.debug("%s - %s: Current effect: %s", self._api_id, self._identifier, self._current_scene)
        return self._current_scene

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        attributes = super().extra_state_attributes or {}
        if self._current_scene:
            attributes["current_scene"] = self._current_scene

        attributes["supports_scenes"] = self._support_scenes
        attributes["available_scenes_count"] = len(self._available_scenes)
        attributes["dynamic_scenes_count"] = len(self._dynamic_scenes)
        attributes["diy_scenes_count"] = len(self._diy_scenes)
        return attributes

    @property
    def state(self) -> str | None:
        """Return the current state of the entity."""
        value = GoveeAPI_GetCachedStateValue(
            self.hass, self._entry_id, self._device_cfg.get("device"), "devices.capabilities.on_off", "powerSwitch"
        )
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
        if not self._support_brightness:
            return None
        value = GoveeAPI_GetCachedStateValue(
            self.hass, self._entry_id, self._device_cfg.get("device"), "devices.capabilities.range", "brightness"
        )
        if value is None:
            return None
        return value_to_brightness(self._brightness_scale, value)

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        if not self._support_color_temp:
            return None
        value = GoveeAPI_GetCachedStateValue(
            self.hass,
            self._entry_id,
            self._device_cfg.get("device"),
            "devices.capabilities.color_setting",
            "colorTemperatureK",
        )
        return value

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color."""
        if not self._support_color:
            return None
        value = GoveeAPI_GetCachedStateValue(
            self.hass, self._entry_id, self._device_cfg.get("device"), "devices.capabilities.color_setting", "colorRgb"
        )
        return self._getRGBfromI(value)

    @property
    def min_color_temp_kelvin(self) -> int:
        """Return the minimum color temperature in Kelvin."""
        if self._temperature_scale:
            return self._temperature_scale[0]
        return 2000

    @property
    def max_color_temp_kelvin(self) -> int:
        """Return the maximum color temperature in Kelvin."""
        if self._temperature_scale:
            return self._temperature_scale[1]
        return 9000

    async def async_turn_on(self, **kwargs) -> None:
        """Async: Turn entity on"""
        try:
            _LOGGER.debug("%s - %s: async_turn_on", self._api_id, self._identifier)
            _LOGGER.debug("%s - %s: async_turn_on: kwargs = %s", self._api_id, self._identifier, kwargs)

            if ATTR_EFFECT in kwargs:
                effect_name = kwargs[ATTR_EFFECT]
                _LOGGER.info("%s - %s: Setting effect: %s", self._api_id, self._identifier, effect_name)

                scene_value = self._scene_value_map.get(effect_name)

                if scene_value is None:
                    for scene in self._dynamic_scenes:
                        if scene.get("name") == effect_name:
                            scene_value = scene.get("value")
                            break

                if scene_value is not None:
                    scene_info = self._scene_value_map.get(effect_name)
                    if isinstance(scene_info, dict) and scene_info.get("type") == "diy":
                        _LOGGER.info(
                            "%s - %s: Sending DIY scene command with value: %s",
                            self._api_id,
                            self._identifier,
                            scene_info["value"],
                        )
                        state_capability = {
                            "type": "devices.capabilities.dynamic_scene",
                            "instance": "diyScene",
                            "value": scene_info["value"],
                        }
                    else:
                        _LOGGER.info(
                            "%s - %s: Sending scene command with value: %s",
                            self._api_id,
                            self._identifier,
                            scene_value,
                        )
                        state_capability = {
                            "type": "devices.capabilities.dynamic_scene",
                            "instance": "lightScene",
                            "value": scene_value,
                        }
                    if await async_GoveeAPI_ControlDevice(
                        self.hass, self._entry_id, self._device_cfg, state_capability
                    ):
                        self._current_scene = effect_name
                        self.async_write_ha_state()
                        _LOGGER.info("%s - %s: Scene set successfully: %s", self._api_id, self._identifier, effect_name)
                else:
                    _LOGGER.warning("%s - %s: Effect not found: %s", self._api_id, self._identifier, effect_name)

            if ATTR_RGB_COLOR in kwargs or ATTR_COLOR_TEMP_KELVIN in kwargs:
                self._current_scene = None

            if ATTR_BRIGHTNESS in kwargs and self._support_brightness:
                state_capability = {
                    "type": "devices.capabilities.range",
                    "instance": "brightness",
                    "value": math.ceil(brightness_to_value(self._brightness_scale, kwargs[ATTR_BRIGHTNESS])),
                }
                if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
                    self.async_write_ha_state()

            if ATTR_COLOR_TEMP_KELVIN in kwargs and self._support_color_temp:
                state_capability = {
                    "type": "devices.capabilities.color_setting",
                    "instance": "colorTemperatureK",
                    "value": kwargs[ATTR_COLOR_TEMP_KELVIN],
                }
                if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
                    self.async_write_ha_state()

            if ATTR_RGB_COLOR in kwargs and self._support_color:
                state_capability = {
                    "type": "devices.capabilities.color_setting",
                    "instance": "colorRgb",
                    "value": self._getIfromRGB(kwargs[ATTR_RGB_COLOR]),
                }
                if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
                    self.async_write_ha_state()

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
            _LOGGER.debug("%s - %s: async_turn_off", self._api_id, self._identifier)
            self._current_scene = None
            state_capability = {
                "type": "devices.capabilities.on_off",
                "instance": "powerSwitch",
                "value": self._state_mapping_set[STATE_OFF],
            }
            if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(
                "%s - %s: async_turn_off failed: %s (%s.%s)",
                self._api_id,
                self._identifier,
                str(e),
                e.__class__.__module__,
                type(e).__name__,
            )

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await super().async_added_to_hass()

        _LOGGER.info(
            "%s - %s: Entity added to hass, loading dynamic scenes if supported", self._api_id, self._identifier
        )

        last_state = await self.async_get_last_state()
        if last_state and last_state.attributes:
            self._current_scene = last_state.attributes.get("current_scene")
            _LOGGER.debug("%s - %s: Restored current scene: %s", self._api_id, self._identifier, self._current_scene)

        if self._has_dynamic_scenes:
            await self._async_update_dynamic_scenes()
            await self._async_update_diy_scenes()

    async def _async_update_diy_scenes(self):
        """Update DIY scenes from API."""
        try:
            _LOGGER.info("%s - %s: Loading DIY scenes from API", self._api_id, self._identifier)

            diy_scenes = await async_GoveeAPI_GetDynamicDIYScenes(self.hass, self._entry_id, self._device_cfg)
            if diy_scenes:
                self._diy_scenes = diy_scenes
                _LOGGER.info("%s - %s: Loaded %d DIY scenes", self._api_id, self._identifier, len(diy_scenes))

                name_counts = {}
                for scene in diy_scenes:
                    scene_name = scene.get("name")
                    scene_value = scene.get("value")
                    if scene_name and scene_value is not None:
                        prefixed = f"DIY: {scene_name}"
                        if prefixed in self._scene_value_map or prefixed in name_counts:
                            count = name_counts.get(prefixed, 1) + 1
                            name_counts[prefixed] = count
                            prefixed = f"{prefixed} ({count})"
                        else:
                            name_counts[prefixed] = 1
                        scene["_display_name"] = prefixed
                        self._scene_value_map[prefixed] = {"value": scene_value, "type": "diy"}
                        _LOGGER.debug(
                            "%s - %s: DIY scene: %s = %s", self._api_id, self._identifier, prefixed, scene_value
                        )
                self.async_write_ha_state()
            else:
                _LOGGER.info("%s - %s: No DIY scenes returned from API", self._api_id, self._identifier)
        except Exception as e:
            _LOGGER.error(
                "%s - %s: _async_update_diy_scenes failed: %s (%s.%s)",
                self._api_id,
                self._identifier,
                str(e),
                e.__class__.__module__,
                type(e).__name__,
            )

    async def _async_update_dynamic_scenes(self):
        """Update dynamic scenes from API."""
        try:
            _LOGGER.info("%s - %s: Loading dynamic scenes from API", self._api_id, self._identifier)

            dynamic_scenes = await async_GoveeAPI_GetDynamicScenes(self.hass, self._entry_id, self._device_cfg)
            if dynamic_scenes:
                self._dynamic_scenes = dynamic_scenes
                _LOGGER.info("%s - %s: Loaded %d dynamic scenes", self._api_id, self._identifier, len(dynamic_scenes))

                for scene in dynamic_scenes:
                    scene_name = scene.get("name")
                    scene_value = scene.get("value")
                    if scene_name and scene_value is not None:
                        self._scene_value_map[scene_name] = scene_value
                        _LOGGER.debug(
                            "%s - %s: Dynamic scene: %s = %s", self._api_id, self._identifier, scene_name, scene_value
                        )
                self.async_write_ha_state()
            else:
                _LOGGER.info("%s - %s: No dynamic scenes returned from API", self._api_id, self._identifier)
        except Exception as e:
            _LOGGER.error(
                "%s - %s: _async_update_dynamic_scenes failed: %s (%s.%s)",
                self._api_id,
                self._identifier,
                str(e),
                e.__class__.__module__,
                type(e).__name__,
            )
