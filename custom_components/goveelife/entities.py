"""Base entities for the Govee Life integration."""

import logging
import os
from datetime import timedelta

import async_timeout

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.const import (
    CONF_FRIENDLY_NAME,
    CONF_PARAMS,
    CONF_SCAN_INTERVAL,
    CONF_STATE,
    CONF_TIMEOUT,
    STATE_UNKNOWN,
)
from .const import DOMAIN, STATE_DEBUG_FILENAME
from .utils import async_GoveeAPI_GetDeviceState

_LOGGER = logging.getLogger(__name__)


class GoveeLifePlatformEntity(CoordinatorEntity, Entity):
    """Base class for Govee Life integration."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, coordinator, device_cfg, **kwargs) -> None:
        """Initialize the entity."""
        try:
            platform = kwargs.get('platform', 'entities')
            self._api_id = str(entry.data.get(CONF_FRIENDLY_NAME, DEFAULT_NAME))
            self._identifier = (str(device_cfg.get('device')).replace(':', '') + '_' + platform).lower()

            _LOGGER.debug("%s - %s: __init__", self._api_id, self._identifier)
            self._device_cfg = device_cfg
            self._entry = entry
            self._entry_id = self._entry.entry_id
            self.hass = hass

            self._name = self._device_cfg.get('deviceName')
            self._entity_id = self._name.lower()
            self.uniqueid = self._identifier + '_' + self._entity_id

            self._attributes = {}
            self._state = STATE_UNKNOWN

            super().__init__(coordinator)

            self._init_platform_specific(**kwargs)
            self.entity_id = generate_entity_id(platform + '.{}', self._entity_id, hass=hass)
            _LOGGER.debug("%s - %s: __init__ complete (uid: %s)", self._api_id, self._identifier, self.uniqueid)

        except Exception as e:
            _LOGGER.error("%s - %s: __init__ failed: %s (%s.%s)", self._api_id, self._identifier, str(e), e.__class__.__module__, type(e).__name__)
            return None

    def _init_platform_specific(self, **kwargs):
        """Platform-specific initialization actions."""
        pass

    @property
    def name(self) -> str | None:
        """Return the name of the entity."""
        return self._name

    @property
    def state(self) -> str | None:
        """Return the current state of the entity."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the entity."""
        return self._attributes

    @property
    def unique_id(self) -> str | None:
        """Return the unique identifier for this entity."""
        return self.uniqueid

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        try:
            entry_data = self.hass.data[DOMAIN][self._entry_id]
            d = self._device_cfg.get('device')
            capabilities = entry_data[CONF_STATE][d].get('capabilities', [])
            for cap in capabilities:
                if cap['type'] == 'devices.capabilities.online':
                    return cap.get('state', {}).get('value', False)
            return False
        except Exception as e:
            _LOGGER.error("%s - available: Failed: %s (%s.%s)", self._entry_id, str(e), e.__class__.__module__, type(e).__name__)
            return False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for device registry."""
        info = DeviceInfo(
            identifiers={(DOMAIN, self._device_cfg.get('device', None))},
            manufacturer=DOMAIN,
            model=self._device_cfg.get('sku', STATE_UNKNOWN),
            name=self._device_cfg.get('deviceName', STATE_UNKNOWN),
            hw_version=str(self._device_cfg.get('type', STATE_UNKNOWN)).split('.')[-1],
        )
        return info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        d = self._device_cfg.get('device')
        state_data = self.hass.data[DOMAIN][self._entry_id][CONF_STATE][d]
        self.async_write_ha_state()


class GoveeAPIUpdateCoordinator(DataUpdateCoordinator):
    """State update coordinator for GoveeAPI."""

    def __init__(self, hass, entry_id, device_cfg):
        """Initialize the coordinator."""
        self._identifier = (str(device_cfg['device']).replace(':', '')) + '_GoveeAPIUpdate'
        _LOGGER.debug("%s - async_GoveeAPI_GetDeviceState: __init__", self._identifier)
        scan_interval = hass.data[DOMAIN][entry_id][CONF_PARAMS][CONF_SCAN_INTERVAL]
        super().__init__(hass, _LOGGER, name=self._identifier, update_interval=timedelta(seconds=scan_interval))
        self._entry_id = entry_id
        self._device_cfg = device_cfg

    async def _async_update_data(self):
        """Fetch data from the API endpoint."""
        try:
            entry_data = self.hass.data[DOMAIN][self._entry_id]
            async with async_timeout.timeout(entry_data[CONF_PARAMS][CONF_TIMEOUT]):
                result = await async_GoveeAPI_GetDeviceState(self.hass, self._entry_id, self._device_cfg, True)
        except Exception as e:
            _LOGGER.error("%s - GoveeAPIUpdateCoordinator: _async_update_data Failed: %s (%s.%s)", self._entry_id, str(e), e.__class__.__module__, type(e).__name__)
            return False

        try:
            scan_interval = entry_data.get(CONF_SCAN_INTERVAL)
            debug_file = os.path.dirname(os.path.realpath(__file__)) + STATE_DEBUG_FILENAME
            if os.path.isfile(debug_file) and scan_interval is None:
                scan_interval = 3600
                _LOGGER.info("%s - GoveeAPIUpdateCoordinator: debug poll interval is %s seconds", DOMAIN, scan_interval)

            if scan_interval is not None:
                scan_interval = timedelta(seconds=scan_interval)
                if scan_interval != self.update_interval:
                    self.update_interval = scan_interval
        except Exception as e:
            _LOGGER.warning("%s - GoveeAPIUpdateCoordinator: _async_update_data update interval change failed: %s (%s.%s)", self._entry_id, str(e), e.__class__.__module__, type(e).__name__)

        if result == 429 or result == 401:
            raise ConfigEntryAuthFailed
