"""Test the Melnor sensors."""

from __future__ import annotations

from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.const import STATE_OFF, STATE_ON

from .conftest import (
    mock_config_entry,
    patch_async_ble_device_from_address,
    patch_async_register_callback,
    patch_melnor_device,
)


async def test_manual_watering_switch_metadata(hass):
    """Test the manual watering switch."""

    entry = mock_config_entry(hass)

    with patch_async_ble_device_from_address(), patch_melnor_device(), patch_async_register_callback():
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        switch = hass.states.get("switch.zone_1")
        assert switch.attributes["device_class"] == SwitchDeviceClass.SWITCH
        assert switch.attributes["icon"] == "mdi:sprinkler"


async def test_manual_watering_switch_on_off(hass):
    """Test the manual watering switch."""

    entry = mock_config_entry(hass)

    with patch_async_ble_device_from_address(), patch_melnor_device() as device_patch, patch_async_register_callback():
        device = device_patch.return_value

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        switch = hass.states.get("switch.zone_1")
        assert switch.state is STATE_OFF

        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.zone_1"},
            blocking=True,
        )

        switch = hass.states.get("switch.zone_1")
        assert switch.state is STATE_ON
        assert device.zone1.is_watering is True

        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": "switch.zone_1"},
            blocking=True,
        )

        switch = hass.states.get("switch.zone_1")
        assert switch.state is STATE_OFF
        assert device.zone1.is_watering is False
