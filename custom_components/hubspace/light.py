import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
)
from homeassistant.util.percentage import percentage_to_ordered_list_item

from .const import DOMAIN, FunctionClass
from .hubspace_base import HubspaceFunction, HubspaceStateValue
from .hubspace_coordinator import HubspaceCoordinator
from .hubspace_entity import HubspaceEntity

_LOGGER = logging.getLogger(__name__)


def _brightness_to_hass(value):
    return int(value * 255) // 100


def _brightness_to_hubspace(value):
    return value * 100 // 255


def _color_temp_to_hass(value) -> int:
    return color_temperature_kelvin_to_mired(float(value[:-1]))


def _color_temp_to_hubspace(value) -> str:
    return f"{color_temperature_mired_to_kelvin(value)}K"


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


class HubspaceLightFunction(HubspaceFunction):
    def _value_key(self, value: Any) -> Any:
        if self.function_class == FunctionClass.COLOR_TEMPERATURE:
            return _color_temp_to_hass(value)
        return value


class HubspaceLightStateValue(HubspaceStateValue):
    def hass_value(self) -> Any | None:
        if self.function_class == FunctionClass.BRIGHTNESS:
            return _brightness_to_hass(self.hubspace_value())
        return super().hass_value()

    def set_hass_value(self, value):
        if self.function_class == FunctionClass.BRIGHTNESS:
            self.set_hubspace_value(_brightness_to_hubspace(value))
        else:
            super().set_hubspace_value(value)


class HubspaceLight(LightEntity, HubspaceEntity):
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._data = self.coordinator.data[self._idx]
        super()._handle_coordinator_update()

    _function_class = HubspaceLightFunction
    _state_value_class = HubspaceLightStateValue

    @property
    def supported_color_modes(self) -> set[str] | None:
        """Flag supported color modes."""
        color_modes = set()
        if FunctionClass.BRIGHTNESS in self.functions:
            color_modes.add(ColorMode.BRIGHTNESS)
        if FunctionClass.COLOR_TEMPERATURE in self.functions:
            color_modes.add(ColorMode.COLOR_TEMP)
        return color_modes

    @property
    def is_on(self) -> bool | None:
        """Return whether the light is on, or if multiple all the lights are on."""
        return self._get_state_value(FunctionClass.POWER, STATE_OFF) == STATE_ON

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return self._get_state_value(FunctionClass.BRIGHTNESS)

    @property
    def color_temp(self) -> int | None:
        """Return the CT color value in mireds."""
        value = self._get_state_value(FunctionClass.COLOR_TEMPERATURE)
        if not value:
            return None
        return _color_temp_to_hass(value)

    @property
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this light supports."""
        hubspace_values = self._get_function_values(FunctionClass.COLOR_TEMPERATURE)
        if not hubspace_values:
            return super().min_mireds
        return _color_temp_to_hass(hubspace_values[0])

    @property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this light supports."""
        hubspace_values = self._get_function_values(FunctionClass.COLOR_TEMPERATURE)
        if not hubspace_values:
            return super().min_mireds
        return _color_temp_to_hass(hubspace_values[-1])

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""

        self._set_state_value(FunctionClass.POWER, STATE_ON)
        if ATTR_BRIGHTNESS in kwargs:
            self._set_state_value(FunctionClass.BRIGHTNESS, kwargs[ATTR_BRIGHTNESS])
        if ATTR_COLOR_TEMP in kwargs:
            self._set_state_value(
                FunctionClass.COLOR_TEMPERATURE,
                percentage_to_ordered_list_item(
                    self._get_function_values(
                        FunctionClass.COLOR_TEMPERATURE, default=[]
                    ),
                    (kwargs[ATTR_COLOR_TEMP] - self.min_mireds)
                    / (self.max_mireds - self.min_mireds)
                    * 100,
                ),
            )
        self._push_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        self._set_state_value(FunctionClass.POWER, STATE_OFF)
        self._push_state()
