"""Platform for sensor integration."""
from __future__ import annotations

import logging

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import HubspaceEntity
from .const import DOMAIN
from .hubspace_coordinator import HubspaceCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the light platform."""

    coordinator: HubspaceCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        HubspaceLight(idx=deviceId, coordinator=coordinator)
        for deviceId in coordinator.lights
    )


class HubspaceLight(LightEntity, HubspaceEntity):
    """A hubspace light."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.hubspace_device = self.coordinator.data[self._idx]

        ## TODO: Create this based on the data, including the supported color temps
        self._attr_supported_color_modes = [
            ColorMode.COLOR_TEMP,
        ]
        self._attr_is_on = (
            self.hubspace_device.stateValue(
                functionClass="power", functionInstance="light-power"
            )
            == "on"
        )

        self._attr_brightness = self.hubspace_device.stateValue(
            functionClass="brightness"
        )

        # 3700K as an expample
        self._attr_color_temp_kelvin = self.hubspace_device.stateValue(
            functionClass="color-temperature"
        )[:-1]

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
