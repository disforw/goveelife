from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_STATE

from custom_components.goveelife.const import DOMAIN
from custom_components.goveelife.utils import async_GoveeAPI_GetDeviceState
from tests.conftest import build_hass_data

DEVICE_CFG = {"sku": "H6117", "device": "AA:BB", "deviceName": "Strip", "capabilities": []}
POST = "custom_components.goveelife.utils.async_GoveeAPI_POSTRequest"


@pytest.fixture
def ready_hass(hass, mock_config_entry, mock_coordinator):
    hass.data = build_hass_data(mock_config_entry, mock_coordinator, DEVICE_CFG)
    return hass


@pytest.mark.parametrize(
    ("post_result", "return_status_code", "expected"),
    [
        (None, False, False),  # API unreachable - issue #148 (NoneType is not subscriptable)
        (None, True, False),
        (429, True, 429),  # rate limited - must reach the coordinator (issue #13)
        (401, True, 401),
        (500, False, False),
        ({"code": 200}, True, False),  # response without payload
    ],
)
async def test_get_device_state_failures(ready_hass, mock_config_entry, post_result, return_status_code, expected):
    with patch(POST, AsyncMock(return_value=post_result)):
        result = await async_GoveeAPI_GetDeviceState(
            ready_hass, mock_config_entry.entry_id, DEVICE_CFG, return_status_code
        )

    assert result == expected
    assert CONF_STATE not in ready_hass.data[DOMAIN][mock_config_entry.entry_id]


async def test_get_device_state_success(ready_hass, mock_config_entry):
    payload = {"sku": "H6117", "device": "AA:BB", "capabilities": []}
    with patch(POST, AsyncMock(return_value={"code": 200, "payload": payload})):
        result = await async_GoveeAPI_GetDeviceState(ready_hass, mock_config_entry.entry_id, DEVICE_CFG, True)

    assert result is True
    assert ready_hass.data[DOMAIN][mock_config_entry.entry_id][CONF_STATE]["AA:BB"] == payload
