"""Helper functions for Govee Life."""

from __future__ import annotations
from typing import Final
import logging
import asyncio
import requests
import json
import os
import uuid
import re
from datetime import date

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import (
    ATTR_DATE,
    CONF_API_KEY,
    CONF_COUNT,
    CONF_PARAMS,
    CONF_STATE,
    CONF_TIMEOUT,
)

from .const import (
    DOMAIN,
    CONF_API_COUNT,
    CLOUD_API_URL_OPENAPI,
    CLOUD_API_HEADER_KEY,
    STATE_DEBUG_FILENAME,
)

_LOGGER: Final = logging.getLogger(__name__)

async def async_ProgrammingDebug(obj, show_all:bool=False) -> None:
    """Async: return all attributes of a specific objec""" 
    try:
        _LOGGER.debug("%s - async_ProgrammingDebug: %s", DOMAIN, obj)
        for attr in dir(obj):
            if attr.startswith('_') and not show_all:
                continue
            if hasattr(obj, attr ):
                _LOGGER.debug("%s - async_ProgrammingDebug: %s = %s", DOMAIN, attr, getattr(obj, attr))
            await asyncio.sleep(0)
    except Exception as e:
        _LOGGER.error("%s - async_ProgrammingDebug: failed: %s (%s.%s)", DOMAIN, str(e), e.__class__.__module__, type(e).__name__)
        pass

def ProgrammingDebug(obj, show_all:bool=False) -> None:
    """return all attributes of a specific objec"""
    try:
        _LOGGER.debug("%s - ProgrammingDebug: %s", DOMAIN, obj)
        for attr in dir(obj):
            if attr.startswith('_') and not show_all:
                continue
            if hasattr(obj, attr ):
                _LOGGER.debug("%s - ProgrammingDebug: %s = %s", DOMAIN, attr, getattr(obj, attr))
    except Exception as e:
        _LOGGER.error("%s - ProgrammingDebug: failed: %s (%s.%s)", DOMAIN, str(e), e.__class__.__module__, type(e).__name__)
        pass

async def async_GooveAPI_CountRequests(hass: HomeAssistant, entry_id: str) -> None:
    """Asnyc: Count daily number of requests to GooveAPI"""       
    try:
        entry_data=hass.data[DOMAIN][entry_id]
        today = date.today()
        #entry_data.setdefault(CONF_API_COUNT, {CONF_COUNT : 0, ATTR_DATE : today})        
        v = entry_data.get(CONF_API_COUNT, {CONF_COUNT : 0, ATTR_DATE : today})        
        if v[ATTR_DATE] == today:
            v[CONF_COUNT] = int(v[CONF_COUNT]) + 1
        else:
            v[CONF_COUNT] = 1           
        entry_data[CONF_API_COUNT] = v
        
        _LOGGER.debug("%s - async_GooveAPI_CountRequests: %s -> %s", entry_id, v[ATTR_DATE], v[CONF_COUNT])
    except Exception as e:
        _LOGGER.error("%s - async_GooveAPI_CountRequests: Failed: %s (%s.%s)", entry_id, str(e), e.__class__.__module__, type(e).__name__)
        return None

async def async_GoveeAPI_GETRequest(hass: HomeAssistant, entry_id: str, path: str) -> None:
    """Asnyc: Request device list via GooveAPI"""
    try:
        debug_file=os.path.dirname(os.path.realpath(__file__))+STATE_DEBUG_FILENAME
        if os.path.isfile(debug_file):
            _LOGGER.debug("%s - async_GoveeAPI_GETRequest: load debug file: %s", entry_id, debug_file)
            with open(debug_file, 'r') as stream:
                payload = json.load(stream)
                return payload['data']['cloud_devices']
    except Exception as e:
        _LOGGER.error("%s - async_GoveeAPI_GETRequest: debug file load failed: %s (%s.%s)", entry_id, str(e), e.__class__.__module__, type(e).__name__)
        return None

    try:
        _LOGGER.debug("%s - async_GoveeAPI_GETRequest: perform api request", entry_id)
        entry_data=hass.data[DOMAIN][entry_id]
        
        #_LOGGER.debug("%s - async_GoveeAPI_GETRequest: perpare parameters for GET request"
        headers={"Content-Type":"application/json",CLOUD_API_HEADER_KEY: str(entry_data[CONF_PARAMS].get(CONF_API_KEY, None))}
        timeout=entry_data[CONF_PARAMS].get(CONF_TIMEOUT, None)
        url=CLOUD_API_URL_OPENAPI + '/' + path.strip("/")

        #_LOGGER.debug("%s - async_GoveeAPI_GETRequest: extecute GET request"
        await async_GooveAPI_CountRequests(hass, entry_id)
        r = await hass.async_add_executor_job(lambda: requests.get(url,headers=headers,timeout=timeout))        
        if r.status_code == 429:
            _LOGGER.error("%s - async_GoveeAPI_GETRequest: Too many API request - limit is 10000/Account/Day", entry_id)
            return None
        elif r.status_code == 401:
            _LOGGER.error("%s - async_GoveeAPI_GETRequest: Unauthorize - check you APIKey", entry_id)
            return None
        elif not r.status_code == 200:
            _LOGGER.error("%s - async_GoveeAPI_GETRequest: Failed: %s", entry_id, str(r.text))
            return None

        _LOGGER.debug("%s - async_GoveeAPI_GETRequest: convert resulting json to object", entry_id)
        return json.loads(r.text)['data']

    except Exception as e:
        _LOGGER.error("%s - async_GoveeAPI_GETRequest: Failed: %s (%s.%s)", entry_id, str(e), e.__class__.__module__, type(e).__name__)
        return None

async def async_GoveeAPI_POSTRequest(hass: HomeAssistant, entry_id: str, path: str, data: str, return_status_code=False) -> None:
    """Asnyc: Perform post state request / control request via GooveAPI"""       
    try:           
        #_LOGGER.debug("%s - async_GoveeAPI_POSTRequest: perform api request", entry_id)
        entry_data=hass.data[DOMAIN][entry_id]
        
        #_LOGGER.debug("%s - async_GoveeAPI_POSTRequest: perpare parameters for POST request"
        headers={"Content-Type":"application/json",CLOUD_API_HEADER_KEY: str(entry_data[CONF_PARAMS].get(CONF_API_KEY, None))}
        timeout=entry_data[CONF_PARAMS].get(CONF_TIMEOUT, None)
        data = re.sub('<dynamic_uuid>', str(uuid.uuid4()), data)
        _LOGGER.debug("%s - async_GoveeAPI_POSTRequest: data = %s", entry_id, data)
        data = json.loads(data)
        url=CLOUD_API_URL_OPENAPI + '/' + path.strip("/")

        #_LOGGER.debug("%s - async_GoveeAPI_POSTRequest: extecute POST request"
        await async_GooveAPI_CountRequests(hass, entry_id)
        r = await hass.async_add_executor_job(lambda: requests.post(url,json=data,headers=headers,timeout=timeout))        
        if r.status_code == 429:
            _LOGGER.error("%s - async_GoveeAPI_POSTRequest: Too many API request - limit is 10000/Account/Day", entry_id)
            if return_status_code == True:
                return r.status_code
            return None
        elif r.status_code == 401:
            _LOGGER.error("%s - async_GoveeAPI_POSTRequest: Unauthorize - check you APIKey", entry_id)
            if return_status_code == True:
                return r.status_code
            return None
        elif not r.status_code == 200:
            _LOGGER.error("%s - async_GoveeAPI_POSTRequest: Failed status_code: %s", entry_id, str(r.text))
            if return_status_code == True:
                return r.status_code
            return None

        #_LOGGER.debug("%s - async_GoveeAPI_POSTRequest: convert resulting json to object", entry_id)
        return json.loads(r.text)

    except Exception as e:
        _LOGGER.error("%s - async_GoveeAPI_POSTRequest: Failed: %s (%s.%s)", entry_id, str(e), e.__class__.__module__, type(e).__name__)
        return None

async def async_GoveeAPI_GetDeviceState(hass: HomeAssistant, entry_id: str, device_cfg, return_status_code=False) -> None:
    """Asnyc: Request and save state of device via GooveAPI"""
    try:
        #_LOGGER.debug("%s - async_GoveeAPI_GetDeviceState: preparing values", entry_id)       
        entry_data=hass.data[DOMAIN][entry_id]
        json_str='{"requestId": "<dynamic_uuid>","payload": {"sku": "' + str(device_cfg.get('sku')) + '","device": "' + str(device_cfg.get('device')) + '"}}'
        r = None
    except Exception as e:
        _LOGGER.error("%s - async_GoveeAPI_GetDeviceState: preparing values failed: %s (%s.%s)", entry_id, str(e), e.__class__.__module__, type(e).__name__)
        return False       
        
    try:
        debug_file=os.path.dirname(os.path.realpath(__file__))+STATE_DEBUG_FILENAME
        if os.path.isfile(debug_file):
            _LOGGER.debug("%s - async_GoveeAPI_GetDeviceState: load debug file: %s", entry_id, debug_file)
            with open(debug_file, 'r') as stream:
                payload = json.load(stream)
                r=payload['data']['cloud_states'][device_cfg.get('device')]
    except Exception as e:
        _LOGGER.error("%s - async_GoveeAPI_GetDeviceState: debug file load failed: %s (%s.%s)", entry_id, str(e), e.__class__.__module__, type(e).__name__)
        return False 
        
    try:
        if r is None:
            r = await async_GoveeAPI_POSTRequest(hass,entry_id, 'device/state', json_str, return_status_code)
            r = r['payload']
        if isinstance(r, int) and return_status_code == True:
            return r
        if not isinstance(r, int):            
            entry_data.setdefault(CONF_STATE, {})
            d=device_cfg.get('device')
            entry_data[CONF_STATE][d] = r
            return True
        return False
        
    except Exception as e:
        _LOGGER.error("%s - async_GoveeAPI_GetDeviceState: Failed: %s (%s.%s)", entry_id, str(e), e.__class__.__module__, type(e).__name__)
        return False

async def async_GoveeAPI_ControlDevice(hass: HomeAssistant, entry_id: str, device_cfg, state_capability, return_status_code=False) -> None:
    """Asnyc: Trigger device action via GooveAPI"""
    try:
        #_LOGGER.debug("%s - async_GoveeAPI_ControlDevice: preparing values", entry_id)       
        entry_data=hass.data[DOMAIN][entry_id]
        state_capability_json = json.dumps(state_capability)
        json_str='{"requestId": "<dynamic_uuid>","payload": {"sku": "' + str(device_cfg.get('sku')) + '","device": "' + str(device_cfg.get('device')) + '","capability": ' + state_capability_json +'}}'
        _LOGGER.debug("%s - async_GoveeAPI_ControlDevice: json_str = %s", entry_id, json_str) 
        r = None
    except Exception as e:
        _LOGGER.error("%s - async_GoveeAPI_ControlDevice: preparing values failed: %s (%s.%s)", entry_id, str(e), e.__class__.__module__, type(e).__name__)
        return False     

    try:
        debug_file=os.path.dirname(os.path.realpath(__file__))+STATE_DEBUG_FILENAME
        if os.path.isfile(debug_file):
            _LOGGER.debug("%s - async_GoveeAPI_ControlDevice: create debug reply", entry_id)
            state_capability['state'] = { "status" : "success" }
            state_capability_json = json.dumps(state_capability)
            r = json.loads('{"requestId": "debug-dummy", "msg": "success", "code": 200, "capability": '+ state_capability_json + '}')
    except Exception as e:
        _LOGGER.error("%s - async_GoveeAPI_GetDeviceState: debug reply failed: %s (%s.%s)", entry_id, str(e), e.__class__.__module__, type(e).__name__)
        return False

    try:
        if r is None:
            r = await async_GoveeAPI_POSTRequest(hass,entry_id, 'device/control', json_str, return_status_code)
        _LOGGER.debug("%s - async_GoveeAPI_ControlDevice: r = %s", entry_id, r)
        if isinstance(r, int) and return_status_code == True:
            return r
        if not isinstance(r, int) and not r.get('capability',None) is None:
            entry_data.setdefault(CONF_STATE, {})
            d=device_cfg.get('device')
            new_cap = r['capability']
            v = new_cap.pop('value')
            new_cap['state'] = { "value" : v }            
            for cap in entry_data[CONF_STATE][d]['capabilities']:
                if cap['type'] == new_cap['type'] and cap['instance'] == new_cap['instance']:                    
                    entry_data[CONF_STATE][d]['capabilities'].remove(cap)
                    entry_data[CONF_STATE][d]['capabilities'].append(new_cap)
                    _LOGGER.debug("%s - async_GoveeAPI_ControlDevice: updated old capability state: %s", entry_id, cap)
                    _LOGGER.debug("%s - async_GoveeAPI_ControlDevice: with new capability state: %s", entry_id, new_cap)
                    return True
        else:
            _LOGGER.warning("%s - async_GoveeAPI_ControlDevice: unhandled api return = %s", entry_id, r)  
        return False

    except Exception as e:
        _LOGGER.error("%s - async_GoveeAPI_ControlDevice: Failed: %s (%s.%s)", entry_id, str(e), e.__class__.__module__, type(e).__name__)
        return False

def GoveeAPI_GetCachedStateValue(hass: HomeAssistant, entry_id: str, device_id, value_type, value_instance):
    """Asnyc: Get value of a state from local cache"""
    try:
        #_LOGGER.debug("%s - async_GoveeAPI_GetCachedStateValue: preparing values", entry_id)       
        entry_data=hass.data[DOMAIN][entry_id]
        capabilities = ((entry_data.get(CONF_STATE)).get(device_id)).get('capabilities',[])
        value=None
    except Exception as e:
        _LOGGER.error("%s - async_GoveeAPI_GetCachedStateValue: Failed: %s (%s.%s)", entry_id, str(e), e.__class__.__module__, type(e).__name__)
        return None

    try:
        #_LOGGER.debug("%s - async_GoveeAPI_GetCachedStateValue: getting value: %s - %s", entry_id, value_type, value_instance)  
        for cap in capabilities:
            if cap['type'] == value_type and cap['instance'] == value_instance:
                cap_state = cap.get('state',None)
                if not cap_state == None:
                    value = cap_state.get('value',cap_state.get(value_instance,None))
        #_LOGGER.debug("%s - async_GoveeAPI_GetCachedStateValue: value: %s = %s", entry_id, value_instance, value)   
        return value
    except Exception as e:
        _LOGGER.error("%s - async_GoveeAPI_GetCachedStateValue: Failed: %s (%s.%s)", entry_id, str(e), e.__class__.__module__, type(e).__name__)
        return None

