"""Switch entities for the Govee Life integration."""

from __future__ import annotations
from typing import Final
import logging
import asyncio
import re

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import CONF_DEVICES, STATE_ON, STATE_OFF, STATE_UNKNOWN

from .entities import GoveeLifePlatformEntity
from .utils import GoveeAPI_GetCachedStateValue, async_GoveeAPI_ControlDevice
from .const import DOMAIN, CONF_COORDINATORS

_LOGGER: Final = logging.getLogger(__name__)
platform = 'switch'

platform_device_types = [
    'devices.types.heater:.*on_off:.*',
    'devices.types.heater:.*toggle:oscillationToggle',
    'devices.types.fan:.*toggle:oscillationToggle',
    'devices.types.socket:.*on_off:.*',
    'devices.types.socket:.*toggle:.*',
    'devices.types.light:.*toggle:gradientToggle',
    'devices.types.ice_maker:.*on_off:.*',
    'devices.types.aroma_diffuser:.*on_off:.*',
    'devices.types.humidifier:.*on_off:.*',
    'devices.types.humidifier:.*toggle:nightlightToggle'
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the switch platform."""
    _LOGGER.debug("Setting up %s platform entry: %s | %s", platform, DOMAIN, entry.entry_id)
    entities = []

    try:
        _LOGGER.debug("%s - async_setup_entry %s: Getting cloud devices from data store", entry.entry_id, platform)
        entry_data = hass.data[DOMAIN][entry.entry_id]
        api_devices = entry_data.get(CONF_DEVICES, [])
    except Exception as e:
        _LOGGER.error("%s - async_setup_entry %s: Getting cloud devices from data store failed: %s (%s.%s)", entry.entry_id, platform, str(e), e.__class__.__module__, type(e).__name__)
        return False

    for device_cfg in api_devices:
        try:
            device = device_cfg.get('device')
            coordinator = entry_data[CONF_COORDINATORS][device]
            for capability in device_cfg.get('capabilities', []):
                capability_key = f"{device_cfg.get('type', STATE_UNKNOWN)}:{capability.get('type', STATE_UNKNOWN)}:{capability.get('instance', STATE_UNKNOWN)}"
                if any(re.match(platform_match, capability_key) for platform_match in platform_device_types):
                    _LOGGER.debug("%s - async_setup_entry %s: Setup capability: %s|%s|%s", entry.entry_id, platform, device, capability.get('type', STATE_UNKNOWN).split('.')[-1], capability.get('instance', STATE_UNKNOWN))
                    entity = GoveeLifeSwitch(hass, entry, coordinator, device_cfg, platform=platform, cap=capability)
                    entities.append(entity)
            await asyncio.sleep(0)
        except Exception as e:
            _LOGGER.error("%s - async_setup_entry %s: Setup device failed: %s (%s.%s)", entry.entry_id, platform, str(e), e.__class__.__module__, type(e).__name__)
            return False

    _LOGGER.info("%s - async_setup_entry: setup %s %s entities", entry.entry_id, len(entities), platform)
    if not entities:
        return None
    async_add_entities(entities)


class GoveeLifeSwitch(GoveeLifePlatformEntity):
    """Switch class for Govee Life integration."""

    _state_mapping = {}
    _state_mapping_set = {}

    def _init_platform_specific(self, **kwargs):
        """Platform specific initialization."""
        self._cap = kwargs.get('cap', None)
        self._name = f"{self._name} {str(self._cap['instance']).capitalize()}"
        self._entity_id = f"{self._entity_id}_{self._cap['instance']}"
        self.uniqueid = f"{self._identifier}_{self._entity_id}"

        for option in self._cap.get('parameters', {}).get('options', []):
            if option['name'] == 'on':
                self._state_mapping[option['value']] = STATE_ON
                self._state_mapping_set[STATE_ON] = option['value']
            elif option['name'] == 'off':
                self._state_mapping[option['value']] = STATE_OFF
                self._state_mapping_set[STATE_OFF] = option['value']
            else:
                _LOGGER.warning("%s - %s: _init_platform_specific: unhandled cap option: %s -> %s", self._api_id, self._identifier, self._cap['type'], option)

    @property
    def state(self) -> str | None:
        """Return the current state of the switch."""
        value = GoveeAPI_GetCachedStateValue(self.hass, self._entry_id, self._device_cfg.get('device'), self._cap.get('type', STATE_UNKNOWN), self._cap.get('instance', STATE_UNKNOWN))
        return self._state_mapping.get(value, STATE_UNKNOWN)

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.state == STATE_ON

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        try:
            _LOGGER.debug("%s - %s: async_turn_on", self._api_id, self._identifier)
            state_capability = {
                "type": self._cap['type'],
                "instance": self._cap['instance'],
                "value": self._state_mapping_set[STATE_ON]
            }
            if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("%s - %s: async_turn_on failed: %s (%s.%s)", self._api_id, self._identifier, str(e), e.__class__.__module__, type(e).__name__)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        try:
            _LOGGER.debug("%s - %s: async_turn_off", self._api_id, self._identifier)
            state_capability = {
                "type": self._cap['type'],
                "instance": self._cap['instance'],
                "value": self._state_mapping_set[STATE_OFF]
            }
            if await async_GoveeAPI_ControlDevice(self.hass, self._entry_id, self._device_cfg, state_capability):
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("%s - %s: async_turn_off failed: %s (%s.%s)", self._api_id, self._identifier, str(e), e.__class__.__module__, type(e).__name__)
