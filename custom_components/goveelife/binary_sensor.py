"""Binary sensor entities for the Govee Life integration."""

from __future__ import annotations

import logging
import re
from typing import Final

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICES,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_COORDINATORS,
    DOMAIN,
)
from .entities import GoveeLifePlatformEntity
from .utils import GoveeAPI_GetCachedStateValue

_LOGGER: Final = logging.getLogger(__name__)
platform = "binary_sensor"

# Match any device type that exposes a devices.capabilities.event capability.
# Extend this list to add device-type-specific filtering if needed.
platform_device_types = [
    r".*:devices\.capabilities\.event:.*",
]

# Map event instance names to appropriate HA binary sensor device classes.
_EVENT_DEVICE_CLASS_MAP: dict[str, BinarySensorDeviceClass] = {
    "waterFullEvent": BinarySensorDeviceClass.PROBLEM,
    "lackWaterEvent": BinarySensorDeviceClass.PROBLEM,
    # Air quality monitor threshold alerts
    "co2AlarmEvent": BinarySensorDeviceClass.GAS,
    # Ice maker state events
    "iceBucketFullEvent": BinarySensorDeviceClass.PROBLEM,
    "iceTrayEmptyEvent": BinarySensorDeviceClass.PROBLEM,
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the binary sensor platform."""
    _LOGGER.debug("Setting up %s platform entry: %s | %s", platform, DOMAIN, entry.entry_id)
    entities = []

    try:
        _LOGGER.debug("%s - async_setup_entry %s: Getting cloud devices from data store", entry.entry_id, platform)
        entry_data = hass.data[DOMAIN][entry.entry_id]
        api_devices = entry_data[CONF_DEVICES]
    except Exception as e:\n        _LOGGER.error(\n            "%s - async_setup_entry %s: Getting cloud devices from data store failed: %s (%s.%s)",
            entry.entry_id,
            platform,
            str(e),
            e.__class__.__module__,
            type(e).__name__,
        )
        return False

    for device_cfg in api_devices:
        try:
            d = device_cfg.get("device")
            coordinator = entry_data[CONF_COORDINATORS][d]
            for capability in device_cfg.get("capabilities", []):
                r = (
                    device_cfg.get("type", STATE_UNKNOWN)
                    + ":"
                    + capability.get("type", STATE_UNKNOWN)
                    + ":"
                    + capability.get("instance", STATE_UNKNOWN)
                )
                setup = any(re.match(pattern, r) for pattern in platform_device_types)
                if setup:
                    _LOGGER.debug(
                        "%s - async_setup_entry %s: Setup capability: %s|%s|%s",
                        entry.entry_id,
                        platform,
                        d,
                        capability.get("type", STATE_UNKNOWN).split(".")[-1],
                        capability.get("instance", STATE_UNKNOWN),
                    )
                    entity = GoveeLifeBinarySensor(
                        hass, entry, coordinator, device_cfg, platform=platform, cap=capability
                    )
                    entities.append(entity)
        except Exception as e:\n            _LOGGER.error(\n                "%s - async_setup_entry %s: Setup device failed: %s (%s.%s)",
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


class GoveeLifeBinarySensor(BinarySensorEntity, GoveeLifePlatformEntity):
    """Binary sensor class for Govee Life integration (event-based capabilities)."""

    def _init_platform_specific(self, **kwargs):
        """Platform specific init actions."""
        cap = kwargs.get("cap")
        self._capability_type = cap.get("type")
        self._capability_name = cap.get("instance")
        self.uniqueid = self._identifier + "_" + self._entity_id + "_" + self._capability_name
        self._name = self._capability_name
        self._attr_device_class = _EVENT_DEVICE_CLASS_MAP.get(self._capability_name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool | None:
        """Return True if the event is active (e.g. water full)."""
        value = GoveeAPI_GetCachedStateValue(
            self.hass,
            self._entry_id,
            self._device_cfg.get("device"),
            self._capability_type,
            self._capability_name,
        )
        _LOGGER.debug("%s - %s: is_on value: %s", self._api_id, self._identifier, value)
        if value is None:
            return None
        return value == 1
