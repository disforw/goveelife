"""Helper functions for Govee Life."""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import date
from typing import Final

import aiohttp
from homeassistant.const import (
    ATTR_DATE,
    CONF_API_KEY,
    CONF_COUNT,
    CONF_PARAMS,
    CONF_STATE,
    CONF_TIMEOUT,
)
from homeassistant.core import HomeAssistant

from .const import (
    CLOUD_API_HEADER_KEY,
    CLOUD_API_URL_OPENAPI,
    CONF_API_COUNT,
    DOMAIN,
    STATE_DEBUG_FILENAME,
)

_LOGGER: Final = logging.getLogger(__name__)


async def async_GoveeAPI_CountRequests(hass: HomeAssistant, entry_id: str) -> None:
    """Async: Count daily number of requests to GoveeAPI"""
    try:
        entry_data = hass.data[DOMAIN][entry_id]
        today = date.today()
        v = entry_data.get(CONF_API_COUNT, {CONF_COUNT: 0, ATTR_DATE: today})
        if v[ATTR_DATE] == today:
            v[CONF_COUNT] = int(v[CONF_COUNT]) + 1
        else:
            v[CONF_COUNT] = 1
        entry_data[CONF_API_COUNT] = v

        _LOGGER.debug("%s - async_GoveeAPI_CountRequests: %s -> %s", entry_id, v[ATTR_DATE], v[CONF_COUNT])
    except Exception as e:
        _LOGGER.error(
            "%s - async_GoveeAPI_CountRequests: Failed: %s (%s.%s)",
            entry_id,
            str(e),
            e.__class__.__module__,
            type(e).__name__,
        )
        return None


async def async_GoveeAPI_GETRequest(hass: HomeAssistant, entry_id: str, path: str) -> None:
    """Async: Request device list via GoveeAPI"""
    try:
        debug_file = os.path.dirname(os.path.realpath(__file__)) + STATE_DEBUG_FILENAME
        if os.path.isfile(debug_file):
            _LOGGER.debug("%s - async_GoveeAPI_GETRequest: load debug file: %s", entry_id, debug_file)
            with open(debug_file) as stream:
                payload = json.load(stream)
                return payload["data"]["cloud_devices"]
    except Exception as e:
        _LOGGER.error(
            "%s - async_GoveeAPI_GETRequest: debug file load failed: %s (%s.%s)",
            entry_id,
            str(e),
            e.__class__.__module__,
            type(e).__name__,
        )
        return None

    try:
        _LOGGER.debug("%s - async_GoveeAPI_GETRequest: perform api request", entry_id)
        entry_data = hass.data[DOMAIN][entry_id]

        headers = {
            "Content-Type": "application/json",
            CLOUD_API_HEADER_KEY: str(entry_data[CONF_PARAMS].get(CONF_API_KEY, None)),
        }
        timeout = entry_data[CONF_PARAMS].get(CONF_TIMEOUT, None)
        url = CLOUD_API_URL_OPENAPI + "/" + path.strip("/")

        await async_GoveeAPI_CountRequests(hass, entry_id)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                if r.status == 429:
                    _LOGGER.error(
                        "%s - async_GoveeAPI_GETRequest: Too many API requests - limit is 10000/Account/Day", entry_id
                    )
                    return None
                elif r.status == 401:
                    _LOGGER.error("%s - async_GoveeAPI_GETRequest: Unauthorized - check your APIKey", entry_id)
                    return None
                elif r.status != 200:
                    text = await r.text()
                    _LOGGER.error("%s - async_GoveeAPI_GETRequest: Failed: %s", entry_id, text)
                    return None

                _LOGGER.debug("%s - async_GoveeAPI_GETRequest: convert resulting json to object", entry_id)
                return (await r.json())["data"]

    except Exception as e:
        _LOGGER.error(
            "%s - async_GoveeAPI_GETRequest: Failed: %s (%s.%s)",
            entry_id,
            str(e),
            e.__class__.__module__,
            type(e).__name__,
        )
        return None


async def async_GoveeAPI_POSTRequest(
    hass: HomeAssistant, entry_id: str, path: str, data: str, return_status_code=False
) -> None:
    """Async: Perform post state request / control request via GoveeAPI"""
    try:
        entry_data = hass.data[DOMAIN][entry_id]

        headers = {
            "Content-Type": "application/json",
            CLOUD_API_HEADER_KEY: str(entry_data[CONF_PARAMS].get(CONF_API_KEY, None)),
        }
        timeout = entry_data[CONF_PARAMS].get(CONF_TIMEOUT, None)
        data = re.sub("<dynamic_uuid>", str(uuid.uuid4()), data)
        _LOGGER.debug("%s - async_GoveeAPI_POSTRequest: data = %s", entry_id, data)
        data = json.loads(data)
        url = CLOUD_API_URL_OPENAPI + "/" + path.strip("/")

        await async_GoveeAPI_CountRequests(hass, entry_id)
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                if r.status == 429:
                    _LOGGER.error(
                        "%s - async_GoveeAPI_POSTRequest: Too many API requests - limit is 10000/Account/Day", entry_id
                    )
                    if return_status_code:
                        return r.status
                    return None
                elif r.status == 401:
                    _LOGGER.error("%s - async_GoveeAPI_POSTRequest: Unauthorized - check your APIKey", entry_id)
                    if return_status_code:
                        return r.status
                    return None
                elif r.status != 200:
                    text = await r.text()
                    _LOGGER.error("%s - async_GoveeAPI_POSTRequest: Failed status_code: %s", entry_id, text)
                    if return_status_code:
                        return r.status
                    return None

                return await r.json()

    except Exception as e:
        _LOGGER.error(
            "%s - async_GoveeAPI_POSTRequest: Failed: %s (%s.%s)",
            entry_id,
            str(e),
            e.__class__.__module__,
            type(e).__name__,
        )
        return None


async def async_GoveeAPI_GetDeviceState(
    hass: HomeAssistant, entry_id: str, device_cfg, return_status_code=False
) -> None:
    """Async: Request and save state of device via GoveeAPI"""
    try:
        entry_data = hass.data[DOMAIN][entry_id]
        json_str = json.dumps(
            {
                "requestId": "<dynamic_uuid>",
                "payload": {
                    "sku": str(device_cfg.get("sku")),
                    "device": str(device_cfg.get("device")),
                },
            }
        )
        r = None
    except Exception as e:
        _LOGGER.error(
            "%s - async_GoveeAPI_GetDeviceState: preparing values failed: %s (%s.%s)",
            entry_id,
            str(e),
            e.__class__.__module__,
            type(e).__name__,
        )
        return False

    try:
        debug_file = os.path.dirname(os.path.realpath(__file__)) + STATE_DEBUG_FILENAME
        if os.path.isfile(debug_file):
            _LOGGER.debug("%s - async_GoveeAPI_GetDeviceState: load debug file: %s", entry_id, debug_file)
            with open(debug_file) as stream:
                payload = json.load(stream)
                r = payload["data"]["cloud_states"][device_cfg.get("device")]
    except Exception as e:
        _LOGGER.error(
            "%s - async_GoveeAPI_GetDeviceState: debug file load failed: %s (%s.%s)",
            entry_id,
            str(e),
            e.__class__.__module__,
            type(e).__name__,
        )
        return False

    try:
        if r is None:
            r = await async_GoveeAPI_POSTRequest(hass, entry_id, "device/state", json_str, return_status_code)
            r = r["payload"]
        if isinstance(r, int) and return_status_code:
            return r
        if not isinstance(r, int):
            entry_data.setdefault(CONF_STATE, {})
            d = device_cfg.get("device")
            entry_data[CONF_STATE][d] = r
            return True
        return False

    except Exception as e:
        _LOGGER.error(
            "%s - async_GoveeAPI_GetDeviceState: Failed: %s (%s.%s)",
            entry_id,
            str(e),
            e.__class__.__module__,
            type(e).__name__,
        )
        return False


async def async_GoveeAPI_ControlDevice(
    hass: HomeAssistant, entry_id: str, device_cfg, state_capability, return_status_code=False
) -> None:
    """Async: Trigger device action via GoveeAPI"""
    try:
        entry_data = hass.data[DOMAIN][entry_id]
        state_capability_json = json.dumps(state_capability)
        json_str = json.dumps(
            {
                "requestId": "<dynamic_uuid>",
                "payload": {
                    "sku": str(device_cfg.get("sku")),
                    "device": str(device_cfg.get("device")),
                    "capability": state_capability,
                },
            }
        )
        _LOGGER.debug("%s - async_GoveeAPI_ControlDevice: json_str = %s", entry_id, json_str)
        r = None
    except Exception as e:
        _LOGGER.error(
            "%s - async_GoveeAPI_ControlDevice: preparing values failed: %s (%s.%s)",
            entry_id,
            str(e),
            e.__class__.__module__,
            type(e).__name__,
        )
        return False

    try:
        debug_file = os.path.dirname(os.path.realpath(__file__)) + STATE_DEBUG_FILENAME
        if os.path.isfile(debug_file):
            _LOGGER.debug("%s - async_GoveeAPI_ControlDevice: create debug reply", entry_id)
            state_capability["state"] = {"status": "success"}
            state_capability_json = json.dumps(state_capability)
            r = json.loads(
                '{"requestId": "debug-dummy", "msg": "success", "code": 200, "capability": '
                + state_capability_json
                + "}"
            )
    except Exception as e:
        _LOGGER.error(
            "%s - async_GoveeAPI_ControlDevice: debug reply failed: %s (%s.%s)",
            entry_id,
            str(e),
            e.__class__.__module__,
            type(e).__name__,
        )
        return False

    try:
        if r is None:
            r = await async_GoveeAPI_POSTRequest(hass, entry_id, "device/control", json_str, return_status_code)
        _LOGGER.debug("%s - async_GoveeAPI_ControlDevice: r = %s", entry_id, r)
        if isinstance(r, int) and return_status_code:
            return r
        if isinstance(r, int):
            # Non-200 status code returned — API rejected the command
            return False
        if r is None:
            _LOGGER.warning("%s - async_GoveeAPI_ControlDevice: API returned None", entry_id)
            return False

        # API call succeeded — attempt best-effort cache update
        if r.get("capability") is not None:
            try:
                entry_data.setdefault(CONF_STATE, {})
                d = device_cfg.get("device")
                new_cap = r["capability"]
                v = new_cap.pop("value")
                new_cap["state"] = {"value": v}
                cache_updated = False
                for cap in entry_data[CONF_STATE][d]["capabilities"]:
                    if cap["type"] == new_cap["type"] and cap["instance"] == new_cap["instance"]:
                        entry_data[CONF_STATE][d]["capabilities"].remove(cap)
                        entry_data[CONF_STATE][d]["capabilities"].append(new_cap)
                        _LOGGER.debug(
                            "%s - async_GoveeAPI_ControlDevice: updated old capability state: %s", entry_id, cap
                        )
                        _LOGGER.debug(
                            "%s - async_GoveeAPI_ControlDevice: with new capability state: %s", entry_id, new_cap
                        )
                        cache_updated = True
                        break
                if not cache_updated:
                    _LOGGER.debug(
                        "%s - async_GoveeAPI_ControlDevice: no matching cap in cache for type=%s instance=%s — skipping cache update",
                        entry_id,
                        new_cap.get("type"),
                        new_cap.get("instance"),
                    )
            except Exception as cache_err:
                _LOGGER.debug(
                    "%s - async_GoveeAPI_ControlDevice: cache update failed (non-fatal): %s",
                    entry_id,
                    str(cache_err),
                )
        else:
            _LOGGER.debug(
                "%s - async_GoveeAPI_ControlDevice: response has no capability key — skipping cache update", entry_id
            )

        # Return True as long as the API accepted the command
        return True

    except Exception as e:
        _LOGGER.error(
            "%s - async_GoveeAPI_ControlDevice: Failed: %s (%s.%s)",
            entry_id,
            str(e),
            e.__class__.__module__,
            type(e).__name__,
        )
        return False


def GoveeAPI_GetCachedStateValue(hass: HomeAssistant, entry_id: str, device_id, value_type, value_instance):
    """Get value of a state from local cache"""
    try:
        entry_data = hass.data[DOMAIN][entry_id]
        capabilities = ((entry_data.get(CONF_STATE)).get(device_id)).get("capabilities", [])
        value = None
    except Exception as e:
        _LOGGER.error(
            "%s - GoveeAPI_GetCachedStateValue: Failed: %s (%s.%s)",
            entry_id,
            str(e),
            e.__class__.__module__,
            type(e).__name__,
        )
        return None

    try:
        for cap in capabilities:
            if cap["type"] == value_type and cap["instance"] == value_instance:
                cap_state = cap.get("state", None)
                if cap_state is not None:
                    value = cap_state.get("value", cap_state.get(value_instance, None))
        return value
    except Exception as e:
        _LOGGER.error(
            "%s - GoveeAPI_GetCachedStateValue: Failed: %s (%s.%s)",
            entry_id,
            str(e),
            e.__class__.__module__,
            type(e).__name__,
        )
        return None


async def async_GoveeAPI_GetDynamicScenes(hass: HomeAssistant, entry_id: str, device_cfg) -> list:
    """Async: Get dynamic scenes for a device via Govee API"""
    try:
        _LOGGER.debug("%s - async_GoveeAPI_GetDynamicScenes: preparing values", entry_id)
        json_str = json.dumps(
            {
                "requestId": str(uuid.uuid4()),
                "payload": {"sku": str(device_cfg.get("sku")), "device": str(device_cfg.get("device"))},
            }
        )

        r = await async_GoveeAPI_POSTRequest(hass, entry_id, "device/scenes", json_str)

        if r and r.get("code") == 200:
            payload = r.get("payload", {})
            capabilities = payload.get("capabilities", [])

            for cap in capabilities:
                if cap.get("type") == "devices.capabilities.dynamic_scene" and cap.get("instance") == "lightScene":
                    options = cap.get("parameters", {}).get("options", [])
                    _LOGGER.debug(
                        "%s - async_GoveeAPI_GetDynamicScenes: found %d dynamic scenes", entry_id, len(options)
                    )
                    return options

        _LOGGER.debug("%s - async_GoveeAPI_GetDynamicScenes: no dynamic scenes found", entry_id)
        return []

    except Exception as e:
        _LOGGER.error(
            "%s - async_GoveeAPI_GetDynamicScenes: Failed: %s (%s.%s)",
            entry_id,
            str(e),
            e.__class__.__module__,
            type(e).__name__,
        )
        return []


async def async_GoveeAPI_GetDynamicDIYScenes(hass: HomeAssistant, entry_id: str, device_cfg) -> list:
    """Async: Get dynamic DIY scenes for a device via Govee API"""
    try:
        _LOGGER.debug("%s - async_GoveeAPI_GetDynamicDIYScenes: preparing values", entry_id)
        json_str = json.dumps(
            {
                "requestId": str(uuid.uuid4()),
                "payload": {"sku": str(device_cfg.get("sku")), "device": str(device_cfg.get("device"))},
            }
        )

        r = await async_GoveeAPI_POSTRequest(hass, entry_id, "device/diy-scenes", json_str)

        if r and r.get("code") == 200:
            payload = r.get("payload", {})
            capabilities = payload.get("capabilities", [])

            for cap in capabilities:
                if cap.get("instance") == "diyScene":
                    options = cap.get("parameters", {}).get("options", [])
                    _LOGGER.debug(
                        "%s - async_GoveeAPI_GetDynamicDIYScenes: found %d DIY scenes", entry_id, len(options)
                    )
                    return options

        _LOGGER.debug("%s - async_GoveeAPI_GetDynamicDIYScenes: no DIY scenes found", entry_id)
        return []

    except Exception as e:
        _LOGGER.error(
            "%s - async_GoveeAPI_GetDynamicDIYScenes: Failed: %s (%s.%s)",
            entry_id,
            str(e),
            e.__class__.__module__,
            type(e).__name__,
        )
        return []


async def async_turn_on_entity(hass: HomeAssistant, entry_id: str, device_cfg, state_mapping_set: dict) -> bool:
    """Shared helper: Turn on a device via on_off capability."""
    state_capability = {
        "type": "devices.capabilities.on_off",
        "instance": "powerSwitch",
        "value": state_mapping_set["on"],
    }
    return await async_GoveeAPI_ControlDevice(hass, entry_id, device_cfg, state_capability)


async def async_turn_off_entity(hass: HomeAssistant, entry_id: str, device_cfg, state_mapping_set: dict) -> bool:
    """Shared helper: Turn off a device via on_off capability."""
    state_capability = {
        "type": "devices.capabilities.on_off",
        "instance": "powerSwitch",
        "value": state_mapping_set["off"],
    }
    return await async_GoveeAPI_ControlDevice(hass, entry_id, device_cfg, state_capability)
