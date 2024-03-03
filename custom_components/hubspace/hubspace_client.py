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

from .const import SETTABLE_FUNCTION_CLASSES, TIMEOUT, FunctionClass, FunctionInstance
from .hubspace_base import HubspaceIdentifiableObject, HubspaceStateValue

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

    def pull_coordinator_data(self) -> dict[str, dict[str, any]]:
        results = self.get_devices()
        indexed_devices: dict[str, dict[str, any]] = {}

        for lis in results:
            if lis.get("typeId") == "metadevice.device":
                indexed_devices[lis.get("id")] = lis

        return indexed_devices

    def set_state(self, metadeviceId: str, values: list[dict[str, Any]]) -> None:
        """Sets the devices current state."""
        auth_token = self.get_auth_token()
        date = datetime.datetime.now(tz=datetime.UTC)
        utc_time = calendar.timegm(date.utctimetuple()) * 1000
        state_payload = {
            "metadeviceId": metadeviceId,
            "values": [value | {"lastUpdateTime": utc_time} for value in values],
        }
        state_url = (
            f"{AFERO_API}/accounts/{self._account_id}/metadevices/{metadeviceId}/state"
        )
        state_header = {
            "user-agent": USER_AGENT,
            "host": AFERO_SEMANTICS_HOST,
            "accept-encoding": "gzip",
            "authorization": f"Bearer {auth_token}",
            "content-type": "application/json; charset=utf-8",
        }
        state_response = requests.put(
            state_url, json=state_payload, headers=state_header, timeout=TIMEOUT
        )
        state_response.close()
        # TODO: set state
        state_response.json()

    def push_state(
        self,
        metadeviceId: str,
        states: dict[FunctionClass, dict[FunctionInstance | None, HubspaceStateValue]],
    ):
        """Pushes the devices current state."""
        auth_token = self.get_auth_token()
        date = datetime.datetime.now(tz=datetime.UTC)
        utc_time = calendar.timegm(date.utctimetuple()) * 1000
        states = [state for states in states.values() for state in states.values()]
        state_payload = {
            "metadeviceId": metadeviceId,
            "values": [
                {
                    "functionClass": state.function_class,
                    "value": state.hubspace_value(),
                    "lastUpdateTime": utc_time,
                }
                | (
                    {"functionInstance": state.function_instance}
                    if state.function_instance
                    else {}
                )
                for state in states
                if state.hubspace_value() is not None
                and state.function_class in SETTABLE_FUNCTION_CLASSES
            ],
        }
        state_url = (
            f"{AFERO_API}/accounts/{self._account_id}/metadevices/{metadeviceId}/state"
        )
        state_header = {
            "user-agent": USER_AGENT,
            "host": AFERO_SEMANTICS_HOST,
            "accept-encoding": "gzip",
            "authorization": f"Bearer {auth_token}",
            "content-type": "application/json; charset=utf-8",
        }
        state_response = requests.put(
            state_url, json=state_payload, headers=state_header, timeout=TIMEOUT
        )
        state_response.close()
        _LOGGER.debug("State payload %s", state_payload)
        _LOGGER.debug("State response %s", state_response.json())
        return state_response.json()
