import logging
from typing import Any


_LOGGER = logging.getLogger(__name__)

from .const import FUNCTION_CLASS, FUNCTION_INSTANCE, FunctionClass, FunctionInstance


class HubspaceObject:
    """Base Hubspace Object which stores data in the form of a dictionary from the Hubspace API response."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    @property
    def raw_data(self) -> dict[str, Any]:
        return self._data


class HubspaceIdentifiableObject(HubspaceObject):
    """A Hubspace object which can be identified by a unique id."""

    @property
    def id(self) -> str | None:
        """Identifier for this object."""
        return self._data.get("id", None)

    @property
    def device_id(self) -> str | None:
        return self._data.get("deviceId", None)

    @property
    def name(self) -> str | None:
        return self._data.get("friendlyName", None)

    @property
    def model(self) -> str | None:
        return self._data.get("description", {}).get("device", {}).get("model", None)

    @property
    def manufacturer(self) -> str | None:
        return (
            self._data.get("description", {})
            .get("device", {})
            .get("manufacturerName", None)
        )

    @property
    def hubspace_device_class(self) -> str | None:
        return (
            self._data.get("description", {}).get("device", {}).get("deviceClass", None)
        )


class HubspaceFunctionKeyedObject(HubspaceObject):
    """A Hubspace object which has a function class."""

    @property
    def function_class(self) -> FunctionClass:
        """Identifier for this objects's function class."""
        return self._data.get(FUNCTION_CLASS, FunctionClass.UNSUPPORTED)

    @property
    def function_instance(self) -> str | None:
        """Identifier for this objects's function instance."""
        return self._data.get(FUNCTION_INSTANCE, None)


class HubspaceFunction(HubspaceFunctionKeyedObject, HubspaceIdentifiableObject):
    """A Hubspace object which defines a function and its possible values."""

    _values: list[Any] | None = None

    @property
    def type(self) -> str | None:
        return self._data.get("type", None)

    @property
    def values(self) -> list[Any]:
        if not self._values:
            self._values = [value.get("name") for value in self._data.get("values", [])]
            self._values.sort(key=self._value_key)
        return self._values

    def _value_key(self, value: Any) -> Any:
        return value


class HubspaceStateValue(HubspaceFunctionKeyedObject):
    """A Hubspace object which defines a particular state value."""

    def hass_value(self) -> Any | None:
        hubspace_value = self.hubspace_value()
        if self.function_class == FunctionClass.AVAILABLE:
            return bool(hubspace_value)
        return hubspace_value

    def set_hass_value(self, value):
        if self.function_class == FunctionClass.AVAILABLE:
            self.set_hubspace_value(str(value))
        else:
            self.set_hubspace_value(value)

    def hubspace_value(self) -> Any | None:
        return self._data.get("value")

    def set_hubspace_value(self, value):
        self._data["value"] = value

    @property
    def last_update_time(self) -> int | None:
        return self._data.get("lastUpdateTime")
