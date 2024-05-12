"""Configuration schema for Govee Life."""

from __future__ import annotations
from typing import Final
import logging
import asyncio
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY,
    CONF_FRIENDLY_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
)
import homeassistant.helpers.config_validation as cv

from .const import (
    DEFAULT_NAME,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER: Final = logging.getLogger(__name__)

GOVEELIFE_SCHEMA: Final = vol.Schema({
    vol.Required(CONF_FRIENDLY_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_API_KEY, default=None): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_POLL_INTERVAL): cv.positive_int,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
})

async def async_get_OPTIONS_GOVEELIFE_SCHEMA(current_data):
    """Async: return an schema object with current values as default""" 
    try:
        _LOGGER.debug("%s - async_get_OPTIONS_GOVEELIFE_SCHEMA", DOMAIN)        
        #_LOGGER.debug("%s - async_get_OPTIONS_GOVEELIFE_SCHEMA: current_data: %s", DOMAIN, current_data)        
        OPTIONS_GOVEELIFE_SCHEMA: Final = vol.Schema({
            vol.Required(CONF_FRIENDLY_NAME, default=current_data.get(CONF_FRIENDLY_NAME,DEFAULT_NAME)): cv.string,
            vol.Required(CONF_API_KEY, default=current_data.get(CONF_API_KEY)): cv.string,
            vol.Optional(CONF_SCAN_INTERVAL, default=current_data.get(CONF_SCAN_INTERVAL,DEFAULT_POLL_INTERVAL)): cv.positive_int,
            vol.Optional(CONF_TIMEOUT, default=current_data.get(CONF_TIMEOUT,DEFAULT_TIMEOUT)): cv.positive_int,
        })
        await asyncio.sleep(0)
        return OPTIONS_GOVEELIFE_SCHEMA
    except Exception as e:
        _LOGGER.error("%s - async_get_OPTIONS_GOVEELIFE_SCHEMA: failed: %s (%s.%s)", DOMAIN, str(e), e.__class__.__module__, type(e).__name__)
        return GOVEELIFE_SCHEMA