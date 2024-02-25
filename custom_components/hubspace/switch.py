"""Platform for sensor integration."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DEVICE_ID
from .hubspace import Hubspace, HubspaceRawDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the fan platform."""

    hub: Hubspace = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        HubspaceSwitch(hubspaceDevice=device)
        for deviceId, device in hub.switches.items()
    )


class HubspaceSwitch(SwitchEntity):
    """A hubspace switch/outlet."""

    _hubspace_device: HubspaceRawDevice

    def __init__(self, hubspaceDevice: HubspaceRawDevice) -> None:
        super().__init__()
        self._hubspace_device = hubspaceDevice
        outletId = (
            ""
            if self._hubspace_device.outletIndex is None
            else f"_{self._hubspace_device.outletIndex}"
        )

        self._attr_unique_id = f"{self._hubspace_device.id}{outletId}"

        self._attr_device_class = (
            SwitchDeviceClass.OUTLET
            if self._hubspace_device.deviceClass == "power-outlet"
            else SwitchDeviceClass.SWITCH
        )

        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, f"{self._hubspace_device.id}"),
            },
            name=f"{self._hubspace_device.friendlyName}",
            manufacturer="Hubspace",
            model=self._hubspace_device.model,
        )

    def turn_on(self) -> None:
        """Turn the entity on."""
        return None

    def turn_off(self) -> None:
        """Turn the entity off."""
        return None
