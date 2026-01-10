"""Config flow for Govee Life."""

from __future__ import annotations

import logging
from typing import Any, Final

from homeassistant import config_entries
from homeassistant.const import (
    CONF_FRIENDLY_NAME,
    CONF_RESOURCE,
)
from homeassistant.core import callback

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
    data: dict[str, Any] | None = None

    def __init__(self):
        """Initialize the config flow handler."""
        _LOGGER.debug("%s - ConfigFlowHandler: __init__", DOMAIN)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle a flow initialized by the user."""
        _LOGGER.debug("%s - ConfigFlowHandler: async_step_user: %s", DOMAIN, user_input)
        try:
            # Removed redundant initialization
            return await self.async_step_resource()
        except Exception as e:
            _LOGGER.error(
                "%s - ConfigFlowHandler: async_step_user failed: %s (%s.%s)",
                DOMAIN,
                str(e),
                e.__class__.__module__,
                type(e).__name__,
            )
            return self.async_abort(reason="exception")

    async def async_step_resource(self, user_input: dict[str, Any] | None = None):
        """Handle resource step in config flow."""
        _LOGGER.debug("%s - ConfigFlowHandler: async_step_resource: %s", DOMAIN, user_input)
        try:
            errors: dict[str, str] = {}
            if user_input is not None:
                _LOGGER.debug("%s - ConfigFlowHandler: async_step_resource add user_input to data", DOMAIN, user_input)
                self.data = user_input
                return await self.async_step_final()
            return self.async_show_form(step_id=CONF_RESOURCE, data_schema=GOVEELIFE_SCHEMA, errors=errors)
            # via the "step_id" the function calls itself after GUI completion
        except Exception as e:
            _LOGGER.error(
                "%s - ConfigFlowHandler: async_step_resource failed: %s (%s.%s)",
                DOMAIN,
                str(e),
                e.__class__.__module__,
                type(e).__name__,
            )
            return self.async_abort(reason="exception")

    async def async_step_final(self, user_input: dict[str, Any] | None = None):
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

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        """Manage the options for Govee Life."""
        _LOGGER.debug("%s - OptionsFlowHandler: async_step_init: %s", DOMAIN, user_input)
        try:
            if not hasattr(self, "data"):
                self.data = {}
            if self.config_entry.source == config_entries.SOURCE_USER:
                return await self.async_step_config_resource()
            else:
                _LOGGER.warning(
                    "%s - OptionsFlowHandler: async_step_init: source not supported: %s",
                    DOMAIN,
                    self.config_entry.source,
                )
                return self.async_abort(reason="not_supported")
        except Exception as e:
            _LOGGER.error(
                "%s - OptionsFlowHandler: async_step_init failed: %s (%s.%s)",
                DOMAIN,
                str(e),
                e.__class__.__module__,
                type(e).__name__,
            )
            return self.async_abort(reason="exception")

    async def async_step_config_resource(self, user_input: dict[str, Any] | None = None):
        """Handle resource configuration step in options flow."""
        _LOGGER.debug("%s - OptionsFlowHandler: async_step_config_resource: %s", DOMAIN, user_input)
        try:
            OPTIONS_GOVEELIFE_SCHEMA = await async_get_OPTIONS_GOVEELIFE_SCHEMA(self.config_entry.data)
            if not user_input:
                return self.async_show_form(step_id="config_resource", data_schema=OPTIONS_GOVEELIFE_SCHEMA)
            _LOGGER.debug("%s - OptionsFlowHandler: async_step_config_resource - user_input: %s", DOMAIN, user_input)
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=user_input, options=self.config_entry.options
            )
            _LOGGER.debug("%s - OptionsFlowHandler: async_step_config_resource complete: %s", DOMAIN, user_input)
            return await self.async_step_final()
        except Exception as e:
            _LOGGER.error(
                "%s - OptionsFlowHandler: async_step_config_resource failed: %s (%s.%s)",
                DOMAIN,
                str(e),
                e.__class__.__module__,
                type(e).__name__,
            )
            return self.async_abort(reason="exception")

    async def async_step_final(self):
        """Handle final step in options flow."""
        try:
            _LOGGER.debug("%s - OptionsFlowHandler: async_step_final", DOMAIN)
            return self.async_create_entry(title="", data={})
            # title=self.data.get(CONF_FRIENDLY_NAME, DEFAULT_NAME)
            # return self.async_create_entry(title=title, data=self.data)
        except Exception as e:
            _LOGGER.error(
                "%s - OptionsFlowHandler: async_step_final failed: %s (%s.%s)",
                DOMAIN,
                str(e),
                e.__class__.__module__,
                type(e).__name__,
            )
            return self.async_abort(reason="exception")
