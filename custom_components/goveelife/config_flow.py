"""Config flow for Govee Life."""

from __future__ import annotations
from typing import Final, Optional, Dict, Any
import logging
import asyncio
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_FRIENDLY_NAME,
    CONF_RESOURCE,
)

from .configuration_schema import (
    GOVEELIFE_SCHEMA,
    async_get_OPTIONS_GOVEELIFE_SCHEMA,
)
from .const import (
    DEFAULT_NAME,
    DOMAIN,
)

_LOGGER: Final = logging.getLogger(__name__)


class ConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Govee Life."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL
    data: Optional[Dict[str, Any]] = None

    def __init__(self):
        """Initialize the config flow handler."""
        _LOGGER.debug("%s - ConfigFlowHandler: __init__", DOMAIN)

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        """Handle a flow initialized by the user."""
        _LOGGER.debug("%s - ConfigFlowHandler: async_step_user: %s", DOMAIN, user_input)
        if self.data is None:
            self.data = {}
        return await self.async_step_resource()

    async def async_step_resource(self, user_input: Optional[Dict[str, Any]] = None):
        """Handle resource step in config flow."""
        _LOGGER.debug("%s - ConfigFlowHandler: async_step_resource: %s", DOMAIN, user_input)
        errors: Dict[str, str] = {}
        if user_input is not None:
            _LOGGER.debug("%s - ConfigFlowHandler: async_step_resource add user_input to data", DOMAIN, user_input)
            self.data = user_input
            return await self.async_step_final()
        return self.async_show_form(step_id=CONF_RESOURCE, data_schema=GOVEELIFE_SCHEMA, errors=errors)

    async def async_step_final(self, user_input: Optional[Dict[str, Any]] = None):
        """Handle final step in config flow."""
        _LOGGER.debug("%s - ConfigFlowHandler: async_step_final: %s", DOMAIN, user_input)
        title = self.data.get(CONF_FRIENDLY_NAME, DEFAULT_NAME)
        return self.async_create_entry(title=title, data=self.data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow handler."""
        _LOGGER.debug("%s: ConfigFlowHandler - async_get_options_flow", DOMAIN)
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Govee Life."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow handler."""
        _LOGGER.debug("%s - OptionsFlowHandler: __init__: %s", DOMAIN, config_entry)
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Manage the options for Govee Life."""
        _LOGGER.debug("%s - OptionsFlowHandler: async_step_init: %s", DOMAIN, user_input)
        if self.config_entry.source == config_entries.SOURCE_USER:
            return await self.async_step_config_resource()
        _LOGGER.warning("%s - OptionsFlowHandler: async_step_init: source not supported: %s", DOMAIN, self.config_entry.source)
        return self.async_abort(reason="not_supported")

    async def async_step_config_resource(self, user_input: Optional[Dict[str, Any]] = None):
        """Handle resource configuration step in options flow."""
        _LOGGER.debug("%s - OptionsFlowHandler: async_step_config_resource: %s", DOMAIN, user_input)
        try:
            OPTIONS_GOVEELIFE_SCHEMA = await async_get_OPTIONS_GOVEELIFE_SCHEMA(self.config_entry.data)
            if not user_input:
                return self.async_show_form(step_id="config_resource", data_schema=OPTIONS_GOVEELIFE_SCHEMA)
            _LOGGER.debug("%s - OptionsFlowHandler: async_step_config_resource - user_input: %s", DOMAIN, user_input)
            self.hass.config_entries.async_update_entry(self.config_entry, data=user_input)
            _LOGGER.debug("%s - OptionsFlowHandler: async_step_config_resource complete: %s", DOMAIN, user_input)
            return await self.async_step_final()
        except Exception as e:
            _LOGGER.error("%s - OptionsFlowHandler: async_step_config_resource failed: %s (%s.%s)", DOMAIN, str(e), e.__class__.__module__, type(e).__name__)
            return self.async_abort(reason="exception")

    async def async_step_final(self):
        """Handle final step in options flow."""
        _LOGGER.debug("%s - OptionsFlowHandler: async_step_final", DOMAIN)
        return self.async_create_entry(title="", data={})
