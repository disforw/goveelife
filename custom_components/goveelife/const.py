"""Constants for Govee Life."""

from __future__ import annotations
from typing import Final

DOMAIN: Final = 'goveelife'
FUNC_OPTION_UPDATES: Final = 'options_update_listener'
SUPPORTED_PLATFORMS: Final = [ "climate","switch","light","fan","sensor", "humidifier" ]
STATE_DEBUG_FILENAME: Final = '/_diagnostics.json'


DEFAULT_TIMEOUT: Final = 10
DEFAULT_POLL_INTERVAL: Final = 60
DEFAULT_NAME: Final = 'GoveeLife'
EVENT_PROPS_ID: Final = DOMAIN + '_property_message'

CONF_COORDINATORS: Final = 'coordinators'
CONF_API_COUNT: Final = 'api_count'
CONF_ENTRY_ID: Final = 'entry_id'

CLOUD_API_URL_DEVELOPER: Final = 'https://developer-api.govee.com/v1/appliance/devices/'
CLOUD_API_URL_OPENAPI: Final = 'https://openapi.api.govee.com/router/api/v1'
CLOUD_API_HEADER_KEY: Final = 'Govee-API-Key'
