"""Diagnostics support for the Govee Life integration."""

from typing import Final, Any
import logging
from importlib_metadata import version

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_DEVICES, CONF_STATE

from .const import DOMAIN

REDACT_CONFIG = {CONF_API_KEY}
REDACT_CLOUD_DEVICES = {'dummy1', 'dummy2'}
REDACT_CLOUD_STATES = {'dummy1', 'dummy2'}

_LOGGER: Final = logging.getLogger(__name__)
platform = 'diagnostics'

async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    """Return diagnostics for a config entry."""
    _LOGGER.debug("Returning %s platform entry: %s", platform, entry.entry_id)
    diag = {}
    
    try:
        _LOGGER.debug("%s - async_get_config_entry_diagnostics %s: Adding config entry configuration to output", entry.entry_id, platform)
        diag["config"] = async_redact_data(entry.as_dict(), REDACT_CONFIG)
    except Exception as e:
        _LOGGER.error("%s - async_get_config_entry_diagnostics %s: Adding config entry configuration to output failed: %s (%s.%s)", entry.entry_id, platform, str(e), e.__class__.__module__, type(e).__name__)
        # return False

    entry_data = hass.data[DOMAIN][entry.entry_id]

    try:
        _LOGGER.debug("%s - async_get_config_entry_diagnostics %s: Adding cloud received device list", entry.entry_id, platform)
        diag["cloud_devices"] = async_redact_data(entry_data.get(CONF_DEVICES, {}), REDACT_CLOUD_DEVICES)
    except Exception as e:
        _LOGGER.error("%s - async_get_config_entry_diagnostics %s: Adding cloud received device list failed: %s (%s.%s)", entry.entry_id, platform, str(e), e.__class__.__module__, type(e).__name__)
        # return False

    try:
        _LOGGER.debug("%s - async_get_config_entry_diagnostics %s: Adding cloud received device states", entry.entry_id, platform)
        diag["cloud_states"] = async_redact_data(entry_data.get(CONF_STATE, {}), REDACT_CLOUD_STATES)
    except Exception as e:
        _LOGGER.error("%s - async_get_config_entry_diagnostics %s: Adding cloud received device states failed: %s (%s.%s)", entry.entry_id, platform, str(e), e.__class__.__module__, type(e).__name__)
        # return False

    try:
        _LOGGER.debug("%s - async_get_config_entry_diagnostics %s: Adding Python module [goveelife] version", entry.entry_id, platform)
        diag["py_module_requests"] = version('requests')
    except Exception as e:
        _LOGGER.error("%s - async_get_config_entry_diagnostics %s: Adding Python module [goveelife] version failed: %s (%s.%s)", entry.entry_id, platform, str(e), e.__class__.__module__, type(e).__name__)
        # return False

    return diag
