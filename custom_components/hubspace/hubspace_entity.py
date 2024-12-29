import logging
from typing import Any, Optional

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, FunctionInstance, FunctionKey
from .hubspace_base import (
    FunctionClass,
    HubspaceFunction,
    HubspaceIdentifiableObject,
    HubspaceStateValue,
)
from .hubspace_coordinator import HubspaceCoordinator

_LOGGER = logging.getLogger(__name__)


class HubspaceEntity(CoordinatorEntity, HubspaceIdentifiableObject):
    """A Hubspace Home assistant entity."""

    _function_class: HubspaceFunction = HubspaceFunction
    _state_value_class: HubspaceStateValue = HubspaceStateValue
    _functions: dict[
        FunctionClass, dict[FunctionInstance | None, HubspaceFunction]
    ] | None = None
    _states: dict[
        FunctionClass, dict[FunctionInstance | None, _state_value_class]
    ] | None = None
    _index: Optional[int] = None

    def __init__(
        self, idx: str, coordinator: HubspaceCoordinator, index: Optional[int] = None
    ) -> None:
        super().__init__(coordinator=coordinator, context=idx)
        self._idx = idx
        self._data = coordinator.data[self._idx]
        self._index = index
        self._coordinator = coordinator

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={
                (DOMAIN, self.device_id),
            },
            name=self.name,
            manufacturer=self.manufacturer,
            model=self.model,
        )

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return self.id

    @property
    def name(self) -> str or None:
        """Return the display name of this device."""
        return self._data.get("friendlyName")

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._get_state_value(FunctionClass.AVAILABLE, default=True)

    @property
    def functions(
        self,
    ) -> dict[FunctionClass, dict[FunctionInstance | None, HubspaceFunction]] | None:
        """Return the functions available for this device."""
        if not self._functions:
            self._functions = {}
            for function in self._data.get("description", {}).get("functions", []):
                hubspace_function = self._function_class(function)
                if hubspace_function.function_class not in self._functions:
                    self._functions[hubspace_function.function_class] = {}
                self._functions[hubspace_function.function_class][
                    hubspace_function.function_instance
                ] = hubspace_function
        return self._functions

    @property
    def states(
        self,
    ) -> dict[FunctionClass, dict[FunctionInstance | None, HubspaceStateValue]]:
        """Return the current states of this device."""
        if not self._states:
            self._set_state(self._data.get("state"))
        return self._states

    def force_load_state_from_data(self):
        self._set_state(self._data.get("state"))

    def _set_state_value(self, key: FunctionKey, value: Any) -> None:
        states = []
        if isinstance(key, tuple):
            state = self.states.get(key[0], {}).get(key[1])
            if state:
                states.append(state)
        else:
            states.extend(self.states.get(key, {}).values())
        for state in states:
            state.set_hass_value(value)

    def _set_state(self, state: dict[str, Any] | None) -> None:
        if state:
            self._states = {}
            for value in state.get("values", []):
                hubspace_state_value = self._state_value_class(value)
                if hubspace_state_value.function_class != FunctionClass.UNSUPPORTED:
                    if hubspace_state_value.function_class not in self._states:
                        self._states[hubspace_state_value.function_class] = {}
                    self._states[hubspace_state_value.function_class][
                        hubspace_state_value.function_instance
                    ] = hubspace_state_value

    def _get_state_value(self, key: FunctionKey, default: Any = None) -> Any:
        [function_class, function_instance] = (
            key if isinstance(key, tuple) else (key, None)
        )
        state_value = None
        if isinstance(key, tuple):
            state_value = self.states.get(function_class, {}).get(function_instance)
        else:
            state_values = list(self.states.get(function_class, {}).values())
            if len(state_values) > 0:
                state_value = state_values[0]
                if len(state_values) > 1:
                    _LOGGER.warning(
                        "Only expected at most one function of this FunctionClass.%s. Attempting to use first",
                        function_class,
                    )
        if state_value:
            return state_value.hass_value()
        return default

    def _get_function_values(self, key: FunctionKey, default: Any = None) -> Any:
        [function_class, function_instance] = (
            key if isinstance(key, tuple) else (key, None)
        )
        function = None
        if isinstance(key, tuple):
            function = self.functions.get(function_class, {}).get(function_instance)
        else:
            functions = list(self.functions.get(function_class, {}).values())
            if len(functions) > 0:
                function = functions[0]
                if len(functions) > 1:
                    _LOGGER.warning(
                        "Only expected at most one function of this FunctionClass.%s. Attempting to use first",
                        function_class,
                    )
        if function:
            return function.values
        return default

    def set_state(self, values: list[dict[str, Any]]) -> None:
        self._set_state(
            self._coordinator.hubspace_client.set_state(
                metadeviceId=self.id, values=values
            )
        )
        self.schedule_update_ha_state()

    def _push_state(
        self,
    ):
        self._set_state(
            self._coordinator.hubspace_client.push_state(
                metadeviceId=self.id, states=self.states
            )
        )
        self.schedule_update_ha_state()
