"""Platform for sensor integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import DOMAIN, TOGGLE_DISABLED, TOGGLE_ENABLED, FunctionClass
from .hubspace_base import HubspaceFunction
from .hubspace_coordinator import HubspaceCoordinator
from .hubspace_entity import HubspaceEntity

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


class HubspaceFanFunction(HubspaceFunction):
    def _value_key(self, value: Any) -> Any:
        if self.function_class == FunctionClass.FAN_SPEED:
            # Sorts fan speeds which have a format "fan-speed-025"
            return int(value[-3:])
        return value


class HubspaceFan(FanEntity, HubspaceEntity):
    """A hubspace fan."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._data = self.coordinator.data[self._idx]
        super()._handle_coordinator_update()

    _function_class = HubspaceFanFunction

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        supported_features = 0
        if FunctionClass.FAN_SPEED in self.functions:
            supported_features |= FanEntityFeature.SET_SPEED
        if FunctionClass.FAN_DIRECTION in self.functions:
            supported_features |= FanEntityFeature.DIRECTION
        if self.preset_modes:
            supported_features |= FanEntityFeature.PRESET_MODE
        return supported_features

    @property
    def is_on(self) -> bool | None:
        """Return whether the fan is on."""
        return self._get_state_value(FunctionClass.POWER, STATE_OFF) == STATE_ON

    @property
    def current_direction(self) -> bool | None:
        """Return whether the fan is on."""
        return self._get_state_value(FunctionClass.FAN_DIRECTION, "forward")

    @property
    def _fan_speed_values(self) -> list[str] | None:
        fan_speed_values = self._get_function_values(FunctionClass.FAN_SPEED)
        if fan_speed_values:
            # Remove off state from list of values.
            return fan_speed_values[1:]
        return None

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        return (
            ordered_list_item_to_percentage(
                self._fan_speed_values,
                self._get_state_value(FunctionClass.FAN_SPEED),
            )
            if self._fan_speed_values
            else None
        )

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return (
            len(self._fan_speed_values)
            if self._fan_speed_values
            else super().speed_count
        )

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., auto, smart, interval, favorite.

        Requires SUPPORT_SET_SPEED.
        """
        for [function_class, function] in self.states.items():
            for [function_instance, state] in function.items():
                if (
                    function_class == FunctionClass.TOGGLE
                    and function_instance is not None
                    and state.hubspace_value() == "enabled"
                ):
                    return function_instance
        return "auto"

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes.

        Requires SUPPORT_SET_SPEED.
        """
        preset_modes = []

        for [function_class, function] in self.states.items():
            for [function_instance, state] in function.items():
                if (
                    function_class == FunctionClass.TOGGLE
                    and function_instance is not None
                ):
                    preset_modes.append(function_instance)

        if preset_modes:
            preset_modes.insert(0, "auto")
        return preset_modes

    def turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs,
    ) -> None:
        """Instruct the light to turn on."""
        self._set_state_value(FunctionClass.POWER, STATE_ON)
        if percentage is not None:
            self._set_state_value(
                FunctionClass.FAN_SPEED,
                percentage_to_ordered_list_item(self._fan_speed_values, percentage),
            )
        if preset_mode is not None:
            self._set_state_value((FunctionClass.TOGGLE, preset_mode), TOGGLE_ENABLED)
        self._push_state()

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        self._set_state_value(
            FunctionClass.FAN_SPEED,
            percentage_to_ordered_list_item(self._fan_speed_values, percentage),
        )
        self._push_state()

    def set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode == "auto":
            for mode in self.preset_modes:
                self._set_state_value((FunctionClass.TOGGLE, mode), TOGGLE_DISABLED)
        else:
            self._set_state_value((FunctionClass.TOGGLE, preset_mode), TOGGLE_ENABLED)
        self._push_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        self._set_state_value(FunctionClass.POWER, STATE_OFF)
        self._push_state()

    def set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        self._set_state_value(FunctionClass.FAN_DIRECTION, direction)
        self._push_state()
