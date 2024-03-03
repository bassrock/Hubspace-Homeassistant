import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, FunctionClass
from .hubspace_coordinator import HubspaceCoordinator
from .hubspace_entity import HubspaceEntity
from .utils import count_key_value

_LOGGER = logging.getLogger(__name__)


def get_indexed_toggle_count(lis: dict[str, Any]) -> int | None:
    device_class = lis.get("description", {}).get("device", {}).get("deviceClass")
    if device_class == "power-outlet":
        return count_key_value(
            lis.get("description", {}).get("functions", []),
            key="functionClass",
            value=FunctionClass.TOGGLE,
        )

    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the fan platform."""

    coordinator: HubspaceCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for deviceId in coordinator.switches:
        device = coordinator.data[deviceId]
        toggle_count = get_indexed_toggle_count(device)
        if toggle_count is None or toggle_count == 1:
            entities.append(HubspaceSwitch(idx=deviceId, coordinator=coordinator))
        else:
            for i in range(1, toggle_count + 1):
                entities.append(
                    HubspaceSwitch(idx=deviceId, coordinator=coordinator, index=i)
                )

    async_add_entities(entities)


class HubspaceSwitch(SwitchEntity, HubspaceEntity):
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._data = self.coordinator.data[self._idx]
        self.force_load_state_from_data()
        super()._handle_coordinator_update()

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        parent_unique_id = super().unique_id
        if self._index is None:
            return parent_unique_id

        return f"{parent_unique_id}_{self._index}"

    @property
    def device_class(self) -> SwitchDeviceClass:
        if self.hubspace_device_class == "power-outlet":
            return SwitchDeviceClass.OUTLET
        return SwitchDeviceClass.SWITCH

    @property
    def is_on(self) -> bool | None:
        """Return whether the light is on, or if multiple all the switches are on."""
        return (
            self._get_state_value(
                (FunctionClass.TOGGLE, f"outlet-{self._index}")
                if self._index is not None
                else FunctionClass.TOGGLE,
                STATE_OFF,
            )
            == STATE_ON
        )

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        self._set_state_value(
            (FunctionClass.TOGGLE, f"outlet-{self._index}")
            if self._index is not None
            else FunctionClass.TOGGLE,
            STATE_ON,
        )
        self._push_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        self._set_state_value(
            (FunctionClass.TOGGLE, f"outlet-{self._index}")
            if self._index is not None
            else FunctionClass.TOGGLE,
            STATE_OFF,
        )
        self._push_state()
