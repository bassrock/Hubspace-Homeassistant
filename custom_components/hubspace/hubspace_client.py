""" Library for interacting with the Hubspace API. """
import base64
import calendar
import datetime
import hashlib
import logging
import os
import re
from typing import Any

import requests

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    DOMAIN,
    FUNCTION_CLASS,
    FUNCTION_INSTANCE,
    SETTABLE_FUNCTION_CLASSES,
    TIMEOUT,
    FunctionClass,
    FunctionInstance,
    FunctionKey,
)

_LOGGER = logging.getLogger(__name__)

AUTH_SESSION_URL = (
    "https://accounts.hubspaceconnect.com/auth/realms/thd/protocol/openid-connect/auth"
)
AUTH_URL = (
    "https://accounts.hubspaceconnect.com/auth/realms/thd/login-actions/authenticate"
)
TOKEN_URL = (
    "https://accounts.hubspaceconnect.com/auth/realms/thd/protocol/openid-connect/token"
)
CLIENT_ID = "hubspace_android"
REDIRECT_URI = "hubspace-app://loginredirect"
USER_AGENT = "Dart/2.15 (dart:io)"
TOKEN_HEADER = {
    "Content-Type": "application/x-www-form-urlencoded",
    "user-agent": USER_AGENT,
    "host": "accounts.hubspaceconnect.com",
}
AFERO_HOST = "api2.afero.net"
AFERO_SEMANTICS_HOST = "semantics2.afero.net"
AFERO_API = "https://api2.afero.net/v1"


class HubspaceClient:
    _refresh_token = None
    _password = None
    _username = None
    _account_id = None
    _last_token = None
    _last_token_time = None
    # Token lasts 120 seconds
    _token_duration = 118 * 1000

    def __init__(self, username, password) -> None:
        """Init the hubspace hub."""
        self._username = username
        self._password = password

    def authenticate(self) -> bool:
        """Test if we can authenticate with the host."""
        self._refresh_token = self.get_refresh_token()
        self._account_id = self.get_account_id()
        return self._refresh_token is not None and self._account_id is not None

    def get_utc_time(self):
        date = datetime.datetime.now(tz=datetime.UTC)
        utc_time = calendar.timegm(date.utctimetuple()) * 1000
        return utc_time

    def get_code_verifier_and_challenge(self):
        code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode("utf-8")
        code_verifier = re.sub("[^a-zA-Z0-9]+", "", code_verifier)
        code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode("utf-8")
        code_challenge = code_challenge.replace("=", "")
        return code_challenge, code_verifier

    def get_auth_session(self):
        [code_challenge, code_verifier] = self.get_code_verifier_and_challenge()

        # defining a params dict for the parameters to be sent to the API
        auth_session_params = {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "scope": "openid offline_access",
        }

        # sending get request and saving the response as response object
        auth_session_response = requests.get(
            url=AUTH_SESSION_URL, params=auth_session_params, timeout=TIMEOUT
        )
        auth_session_response.close()

        session_code = re.search(
            "session_code=(.+?)&", auth_session_response.text
        ).group(1)
        execution = re.search("execution=(.+?)&", auth_session_response.text).group(1)
        tab_id = re.search("tab_id=(.+?)&", auth_session_response.text).group(1)
        auth_cookies = auth_session_response.cookies.get_dict()
        return [session_code, execution, tab_id, auth_cookies, code_verifier]

    def get_refresh_token(self):
        [
            session_code,
            execution,
            tab_id,
            auth_cookies,
            code_verifier,
        ] = self.get_auth_session()

        auth_url = f"{AUTH_URL}?client_id={CLIENT_ID}&session_code={session_code}&execution={execution}&tab_id={tab_id}"
        auth_header = {
            "Content-Type": "application/x-www-form-urlencoded",
            "user-agent": "Mozilla/5.0 (Linux; Android 7.1.1; Android SDK built for x86_64 Build/NYC) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36",
        }
        auth_data = {
            "username": self._username,
            "password": self._password,
            "credentialId": "",
        }
        auth_response = requests.post(
            auth_url,
            data=auth_data,
            headers=auth_header,
            cookies=auth_cookies,
            allow_redirects=False,
            timeout=TIMEOUT,
        )
        auth_response.close()

        location = auth_response.headers.get("location")
        code = re.search("&code=(.+?)$", location).group(1)

        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": code_verifier,
            "client_id": CLIENT_ID,
        }
        token_response = requests.post(
            TOKEN_URL, data=token_data, headers=TOKEN_HEADER, timeout=TIMEOUT
        )
        token_response.close()
        return token_response.json().get("refresh_token")

    def get_auth_token(self):
        utc_time = self.get_utc_time()

        if self._last_token is not None and (
            (utc_time - self._last_token_time) < self._token_duration
        ):
            _LOGGER.debug("Resusing auth token")
            return self._last_token

        token_data = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "scope": "openid email offline_access profile",
            "client_id": CLIENT_ID,
        }
        token_response = requests.post(
            TOKEN_URL, data=token_data, headers=TOKEN_HEADER, timeout=TIMEOUT
        )
        token_response.close()
        token = token_response.json().get("id_token")
        self._last_token = token
        self._last_token_time = utc_time

        return token

    def get_account_id(self):
        account_url = f"{AFERO_API}/users/me"
        account_header = {
            "user-agent": USER_AGENT,
            "host": AFERO_HOST,
            "accept-encoding": "gzip",
            "authorization": f"Bearer {self.get_auth_token()}",
        }
        account_data = {}
        account_response = requests.get(
            account_url, data=account_data, headers=account_header, timeout=TIMEOUT
        )
        account_response.close()
        return (
            account_response.json()
            .get("accountAccess")[0]
            .get("account")
            .get("accountId")
        )

    def get_devices(self):
        children_url = (
            f"{AFERO_API}/accounts/{self._account_id}/metadevices?expansions=state"
        )
        children_header = {
            "user-agent": USER_AGENT,
            "host": AFERO_SEMANTICS_HOST,
            "accept-encoding": "gzip",
            "authorization": f"Bearer {self.get_auth_token()}",
        }
        children_data = {}
        children_response = requests.get(
            children_url, data=children_data, headers=children_header, timeout=TIMEOUT
        )
        children_response.close()

        return children_response.json()

    def pull_coordinator_data(self):
        results = self.get_devices()

        indexed_devices = {}

        # loop again to get all the devices that do no have childen.
        for lis in results:
            if lis.get("typeId") == "metadevice.device":
                device_id = lis.get("id")
                device_class = (
                    lis.get("description", {}).get("device", {}).get("deviceClass")
                )
                functions = lis.get("description", {}).get("functions", [])
                ## TODO re-add code to make outlet switch work..
                indexed_devices[device_id] = lis
        return indexed_devices


class HubspaceObject:
    """Base Hubspace Object which stores data in the form of a dictionary from the Hubspace API response."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data


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

    def __init__(self, idx: str, coordinator: DataUpdateCoordinator) -> None:
        super().__init__(coordinator=coordinator, context=idx)
        self._idx = idx
        self._data = coordinator.data[self._idx]
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
    def name(self) -> str | None:
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

    # def update(self) -> None:
    #     """Update this devices current state."""
    #     if self._skip_next_update:
    #         self._skip_next_update = False
    #         return
    #     auth_token = get_auth_token(self._refresh_token)
    #     state_url = (
    #         f"{AFERO_API}/accounts/{self._account_id}/metadevices/{self.id}/state"
    #     )
    #     state_header = {
    #         "user-agent": USER_AGENT,
    #         "host": AFERO_SEMANTICS_HOST,
    #         "accept-encoding": "gzip",
    #         "authorization": f"Bearer {auth_token}",
    #     }
    #     state_response = requests.get(state_url, headers=state_header)
    #     state_response.close()
    #     self._set_state(state_response.json())

    # def set_state(self, values: list[dict[str, Any]]) -> None:
    #     """Sets the devices current state."""
    #     auth_token = get_auth_token(self._refresh_token)
    #     date = datetime.datetime.now(tz=datetime.utc)
    #     utc_time = calendar.timegm(date.utctimetuple()) * 1000
    #     state_payload = {
    #         "metadeviceId": self.id,
    #         "values": [value | {"lastUpdateTime": utc_time} for value in values],
    #     }
    #     state_url = (
    #         f"{AFERO_API}/accounts/{self._account_id}/metadevices/{self.id}/state"
    #     )
    #     state_header = {
    #         "user-agent": USER_AGENT,
    #         "host": AFERO_SEMANTICS_HOST,
    #         "accept-encoding": "gzip",
    #         "authorization": f"Bearer {auth_token}",
    #         "content-type": "application/json; charset=utf-8",
    #     }
    #     state_response = requests.put(
    #         state_url, json=state_payload, headers=state_header, timeout=TIMEOUT
    #     )
    #     state_response.close()
    #     self._set_state(state_response.json())
    #     self._skip_next_update = True

    # def _push_state(self):
    #     """Pushes the devices current state."""
    #     auth_token = get_auth_token(self._refresh_token)
    #     date = datetime.datetime.now(tz=datetime.utc)
    #     utc_time = calendar.timegm(date.utctimetuple()) * 1000
    #     states = [state for states in self.states.values() for state in states.values()]
    #     state_payload = {
    #         "metadeviceId": self.id,
    #         "values": [
    #             {
    #                 "functionClass": state.function_class,
    #                 "value": state.hubspace_value(),
    #                 "lastUpdateTime": utc_time,
    #             }
    #             | (
    #                 {"functionInstance": state.function_instance}
    #                 if state.function_instance
    #                 else {}
    #             )
    #             for state in states
    #             if state.hubspace_value() is not None
    #             and state.function_class in SETTABLE_FUNCTION_CLASSES
    #         ],
    #     }
    #     state_url = (
    #         f"{AFERO_API}/accounts/{self._account_id}/metadevices/{self.id}/state"
    #     )
    #     state_header = {
    #         "user-agent": USER_AGENT,
    #         "host": AFERO_SEMANTICS_HOST,
    #         "accept-encoding": "gzip",
    #         "authorization": f"Bearer {auth_token}",
    #         "content-type": "application/json; charset=utf-8",
    #     }
    #     state_response = requests.put(
    #         state_url, json=state_payload, headers=state_header, timeout=TIMEOUT
    #     )
    #     state_response.close()
    #     _LOGGER.debug("State payload %s", state_payload)
    #     _LOGGER.debug("State response %s", state_response.json())
    #     self._set_state(state_response.json())
    #     self._skip_next_update = True

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

    def _set_state(self, state: dict[str, Any] or None) -> None:
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