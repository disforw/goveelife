"""Select entities for the Govee Life integration."""

from __future__ import annotations

import logging
import re
from typing import Final

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICES, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .const import CONF_COORDINATORS, DOMAIN
from .entities import GoveeLifePlatformEntity
from .utils import GoveeAPI_GetCachedStateValue, async_GoveeAPI_ControlDevice

_LOGGER: Final = logging.getLogger(__name__)
platform = "select"

platform_device_types = [
    ".*:devices.capabilities.mode:.*",
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up the select platform."""
    _LOGGER.debug("Setting up %s platform entry: %s | %s", platform, DOMAIN, entry.entry_id)
    entities = []

    try:
        _LOGGER.debug("%s - async_setup_entry %s: Getting cloud devices from data store", entry.entry_id, platform)
        entry_data = hass.data[DOMAIN][entry.entry_id]
        api_devices = entry_data.get(CONF_DEVICES, [])
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
            device = device_cfg.get("device")
            coordinator = entry_data[CONF_COORDINATORS][device]
            for capability in device_cfg.get("capabilities", []):
                capability_key = (
                    f"{device_cfg.get('type', STATE_UNKNOWN)}"
                    f":{capability.get('type', STATE_UNKNOWN)}"
                    f":{capability.get('instance', STATE_UNKNOWN)}"
                )
                if any(re.match(platform_match, capability_key) for platform_match in platform_device_types):
                    # Only create a select if there are named options to choose from
                    options = capability.get("parameters", {}).get("options", [])
                    if not options:
                        continue
                    _LOGGER.debug(
                        "%s - async_setup_entry %s: Setup capability: %s|%s|%s",
                        entry.entry_id,
                        platform,
                        device,
                        capability.get("type", STATE_UNKNOWN).split(".")[-1],
                        capability.get("instance", STATE_UNKNOWN),
                    )
                    entity = GoveeLifeSelect(hass, entry, coordinator, device_cfg, platform=platform, cap=capability)
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


class GoveeLifeSelect(SelectEntity, GoveeLifePlatformEntity):
    """Select entity for Govee Life mode capabilities (e.g. HDMI source)."""

    def _init_platform_specific(self, **kwargs) -> None:
        """Platform specific initialization."""
        self._cap = kwargs.get("cap", None)
        instance = self._cap.get("instance", "mode")
        # Make the display name human-friendly
        display_instance = instance.replace("hdmiSource", "HDMI Source")
        self._name = f"{self._name} {display_instance}"
        self._entity_id = f"{self._entity_id}_{instance}"
        self.uniqueid = f"{self._identifier}_{self._entity_id}"

        options = self._cap.get("parameters", {}).get("options", [])
        self._option_to_value: dict[str, int | str] = {
            option["name"]: option["value"]
            for option in options
            if option.get("name") is not None and option.get("value") is not None
        }
        self._value_to_option: dict[int | str, str] = {v: k for k, v in self._option_to_value.items()}
        self._attr_options = list(self._option_to_value.keys())

        _LOGGER.info(
            "%s - %s: _init_platform_specific: select options: %s",
            self._api_id,
            self._identifier,
            self._attr_options,
        )

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        value = GoveeAPI_GetCachedStateValue(
            self.hass,
            self._entry_id,
            self._device_cfg.get("device"),
            self._cap.get("type", STATE_UNKNOWN),
            self._cap.get("instance", STATE_UNKNOWN),
        )
        return self._value_to_option.get(value)

    async def async_select_option(self, option: str) -> None:
        """Select a new option."""
        try:
            _LOGGER.debug("%s - %s: async_select_option: %s", self._api_id, self._identifier, option)
            if option not in self._option_to_value:
                _LOGGER.error(
                    "%s - %s: async_select_option: invalid option: %s",
                    self._api_id,
                    self._identifier,
                    option,
                )
                return
            state_capability = {
                "type": self._cap["type"],
                "instance": self._cap["instance"],
                "value": self._option_to_value[option],
            }
            if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(
                "%s - %s: async_select_option failed: %s (%s.%s)",
                self._api_id,
                self._identifier,
                str(e),
                e.__class__.__module__,
                type(e).__name__,
            )
