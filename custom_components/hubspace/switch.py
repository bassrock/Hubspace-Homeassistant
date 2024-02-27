"""Platform for sensor integration."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .base import HubspaceEntity
from .const import DOMAIN
from .hubspace_coordinator import HubspaceCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""

    coordinator: HubspaceCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        HubspaceSwitch(idx=deviceId, coordinator=coordinator)
        for deviceId in coordinator.switches
    )


class HubspaceSwitch(SwitchEntity, HubspaceEntity):
    """A hubspace switch/outlet."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.hubspace_device = self.coordinator.data[self._idx]
        self._attr_device_class = (
            SwitchDeviceClass.OUTLET
            if self.hubspace_device.deviceClass == "power-outlet"
            else SwitchDeviceClass.SWITCH
        )

        if self.hubspace_device.outletIndex is not None:
            self._attr_is_on = (
                self.hubspace_device.stateValue(
                    functionClass="toggle",
                    functionInstance=f"outlet-{self.hubspace_device.outletIndex}",
                )
                == "on"
            )
        else:
            self._attr_is_on = (
                self.hubspace_device.stateValue(functionClass="power") == "on"
            )

        try:
            self.async_write_ha_state()
        except:
            _LOGGER.debug("could not write ha state, likely init")

    def turn_on(self) -> None:
        """Turn the entity on."""
        return None

    def turn_off(self) -> None:
        """Turn the entity off."""
        return None
