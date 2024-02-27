"""Platform for sensor integration."""
from __future__ import annotations

import logging

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .base import HubspaceEntity
from .const import DOMAIN
from .hubspace_coordinator import HubspaceCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the fan platform."""

    coordinator: HubspaceCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        HubspaceFan(idx=deviceId, coordinator=coordinator)
        for deviceId in coordinator.fans
    )


class HubspaceFan(HubspaceEntity, FanEntity):
    """A hubspace fan."""

    fanSpeedNames = []

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.hubspace_device = self.coordinator.data[self._idx]

        self._attr_supported_features = [
            FanEntityFeature.DIRECTION,
            FanEntityFeature.OSCILLATE,
            FanEntityFeature.PRESET_MODE,
            FanEntityFeature.SET_SPEED,
        ]
        self._attr_is_on = (
            self.hubspace_device.stateValue(
                functionClass="power", functionInstance="fan-power"
            )
            == "on"
        )

        self._attr_preset_modes = ["Comfort Breeze"]

        self.fanSpeedNames = self.hubspace_device.functionValues(
            functionClass="fan-speed", functionInstance="fan-speed"
        )
        if "fan-speed-000" in self.fanSpeedNames:
            self.fanSpeedNames.remove("fan-speed-000")

        self._attr_speed_count = len(self.fanSpeedNames)

        if self._attr_is_on:
            self._attr_percentage = ordered_list_item_to_percentage(
                self.fanSpeedNames,
                self.hubspace_device.stateValue(
                    functionClass="fan-speed", functionInstance="fan-speed"
                ),
            )
        else:
            self._attr_percentage = 0

        # the hubspace values match the HA constants of forward and reverse
        self._attr_current_direction = self.hubspace_device.stateValue(
            functionClass="fan-reverse", functionInstance="fan-reverse"
        )
        try:
            self.async_write_ha_state()
        except:
            _LOGGER.debug("could not write ha state, likely init")
