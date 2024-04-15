"""Support for dScriptModule services."""

from __future__ import annotations
from typing import Final
import logging
import asyncio
import functools

import time
import datetime

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.const import (
    CONF_SCAN_INTERVAL,
)

from .const import (
    DOMAIN,
    CONF_ENTRY_ID,
)

_LOGGER: Final = logging.getLogger(__name__)


async def async_registerService(hass: HomeAssistant, name:str , service) -> None:
    """Register a service if it does not already exist"""
    try:
        _LOGGER.debug("%s - async_registerService: %s", DOMAIN, name)
        await asyncio.sleep(0)        
        if not hass.services.has_service(DOMAIN, name):
            #_LOGGER.info("%s - async_registerServic: register service: %s", DOMAIN, name)
            #hass.services.async_register(DOMAIN, name, service)
            hass.services.async_register(DOMAIN, name, functools.partial(service, hass))
        else:
            _LOGGER.debug("%s - async_registerServic: service already exists: %s", DOMAIN, name)  
    except Exception as e:
        _LOGGER.error("%s - async_registerService: failed: %s (%s.%s)", DOMAIN, str(e), e.__class__.__module__, type(e).__name__)        


async def async_service_SetPollInterval(hass: HomeAssistant, call: ServiceCall) -> None:
    """Service to set the poll interval to reduece requests"""
    try:
        scan_interval = call.data.get(CONF_SCAN_INTERVAL, None)
        if scan_interval is None:
            _LOGGER.error("%s - async_service_SetPollInterval: %s is a required parameter", DOMAIN, CONF_SCAN_INTERVAL)
            return None

        entry_id = call.data.get(CONF_ENTRY_ID, None)
        if entry_id is None:
            _LOGGER.error("%s - async_service_SetPollInterval: %s is a required parameter", DOMAIN, CONF_ENTRY_ID)
            return None

        hass.data[DOMAIN][entry_id][CONF_SCAN_INTERVAL] = scan_interval
        _LOGGER.info("%s - async_service_SetPollInterval: Poll interval updated to %s seconds - change active after next poll", DOMAIN, scan_interval)

    except Exception as e:
        _LOGGER.error("%s - async_service_SetPollInterval: %s failed: %s (%s.%s)", DOMAIN, call, str(e), e.__class__.__module__, type(e).__name__)

