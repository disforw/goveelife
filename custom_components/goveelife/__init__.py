"""Init for the Govee Life integration."""

from __future__ import annotations
from typing import Final
import logging
import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import (
    CONF_API_KEY,
    CONF_DEVICES,
    CONF_PARAMS,
    CONF_SCAN_INTERVAL,
)

from .const import (
    DOMAIN,
    CONF_COORDINATORS,
    FUNC_OPTION_UPDATES,
    SUPPORTED_PLATFORMS,
)
from .entities import (
    GoveeAPIUpdateCoordinator,
)
from .services import (
    async_registerService,
    async_service_SetPollInterval,
)
from .utils import (
    async_ProgrammingDebug,
    async_GoveeAPI_GETRequest,
    async_GoveeAPI_GetDeviceState,
)

_LOGGER: Final = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up cloud resource from the config entry."""
    _LOGGER.debug("Setting up config entry: %s", entry.entry_id)

    try:
        _LOGGER.debug("%s - async_setup_entry: Creating data store: %s.%s ", entry.entry_id, DOMAIN, entry.entry_id)
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN].setdefault(entry.entry_id, {})
        entry_data = hass.data[DOMAIN][entry.entry_id]
        entry_data[CONF_PARAMS] = entry.data
        entry_data[CONF_SCAN_INTERVAL] = None
    except Exception as e:
        _LOGGER.error("%s - async_setup_entry: Creating data store failed: %s (%s.%s)", entry.entry_id, str(e), e.__class__.__module__, type(e).__name__)
        return False

    try:
        _LOGGER.debug("%s - async_setup_entry: Receiving cloud devices..", entry.entry_id)
        api_devices = await async_GoveeAPI_GETRequest(hass, entry.entry_id, 'user/devices')
        if api_devices is None:
            return False
        entry_data[CONF_DEVICES] = api_devices
    except Exception as e:
        _LOGGER.error("%s - async_setup_entry: Receiving cloud devices failed: %s (%s.%s)", entry.entry_id, str(e), e.__class__.__module__, type(e).__name__)
        return False 

    try:
        _LOGGER.debug("%s - async_setup_entry: Creating update coordinators per device..", entry.entry_id)
        entry_data.setdefault(CONF_COORDINATORS, {})
        for device_cfg in api_devices:
            await async_GoveeAPI_GetDeviceState(hass, entry.entry_id, device_cfg)
            coordinator = GoveeAPIUpdateCoordinator(hass, entry.entry_id, device_cfg)
            d = device_cfg.get('device')
            entry_data[CONF_COORDINATORS][d] = coordinator            
    except Exception as e:
        _LOGGER.error("%s - async_setup_entry: Creating update coordinators failed: %s (%s.%s)", entry.entry_id, str(e), e.__class__.__module__, type(e).__name__)
        return False 

    try:
        _LOGGER.debug("%s - async_setup_entry: Register option updates listener: %s ", entry.entry_id, FUNC_OPTION_UPDATES)
        entry_data[FUNC_OPTION_UPDATES] = entry.add_update_listener(options_update_listener)
    except Exception as e:
        _LOGGER.error("%s - async_setup_entry: Register option updates listener failed: %s (%s.%s)", entry.entry_id, str(e), e.__class__.__module__, type(e).__name__)
        return False

    try:
        await hass.config_entries.async_forward_entry_setups(entry, SUPPORTED_PLATFORMS)
    except Exception as e:
        _LOGGER.error("%s - async_setup_entry: Setup trigger for platform failed: %s (%s.%s)", entry.entry_id, str(e), e.__class__.__module__, type(e).__name__)
        return False

    try:
        _LOGGER.debug("%s - async_setup_entry: register services", entry.entry_id)
        await async_registerService(hass, "set_poll_interval", async_service_SetPollInterval)
    except Exception as e:
        _LOGGER.error("%s - async_setup_entry: register services failed: %s (%s.%s)", entry.entry_id, str(e), e.__class__.__module__, type(e).__name__)
        return False 

    _LOGGER.debug("%s - async_setup_entry: Completed", entry.entry_id)
    return True

async def options_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle options update."""
    _LOGGER.debug("Update options / reload config entry: %s", entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    try:
        _LOGGER.debug("Unloading config entry: %s", entry.entry_id)
        all_ok = True
        for platform in SUPPORTED_PLATFORMS:
            _LOGGER.debug("%s - async_unload_entry: unload platform: %s", entry.entry_id, platform)
            platform_ok = await hass.config_entries.async_forward_entry_unload(entry, platform)
            if not platform_ok:
                _LOGGER.error("%s - async_unload_entry: failed to unload: %s (%s)", entry.entry_id, platform, platform_ok)
                all_ok = platform_ok

        if all_ok:
            _LOGGER.debug("%s - async_unload_entry: Unload option updates listener: %s.%s ", entry.entry_id, FUNC_OPTION_UPDATES)
            hass.data[DOMAIN][entry.entry_id][FUNC_OPTION_UPDATES]()
            _LOGGER.debug("%s - async_unload_entry: Remove data store: %s.%s ", entry.entry_id, DOMAIN, entry.entry_id)
            hass.data[DOMAIN].pop(entry.entry_id)
        return all_ok
    except Exception as e:
        _LOGGER.error("%s - async_unload_entry: Unload device failed: %s (%s.%s)", entry.entry_id, str(e), e.__class__.__module__, type(e).__name__)
        return False
