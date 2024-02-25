import asyncio
import base64
import calendar
import copy
import datetime
import hashlib
import json
import logging
import os
import re
from typing import Optional

import requests

from .const import TIMEOUT

_LOGGER = logging.getLogger(__name__)


class HubspaceRawDevice:
    deviceClass: str  # fan, switch, light, power-outlet, ceiling-fan
    id: str
    deviceId: str
    deviceId: str
    model: str
    friendlyName: str
    functions: list[dict[str, any]]
    state: list[dict[str, any]]
    outletIndex: Optional[int]
    children: list["HubspaceRawDevice"] = []

    def __init__(
        self,
        id: str,
        deviceId: str,
        model: str,
        deviceClass: str,
        friendlyName: str,
        functions: list[dict[str, any]],
        state: list[dict[str, any]],
        outletIndex: Optional[int] = None,
    ) -> None:
        self.id = id
        self.deviceId = deviceId
        self.model = model
        self.deviceClass = deviceClass
        self.friendlyName = friendlyName
        self.functions = functions
        self.state = state
        self.outletIndex = outletIndex
        self

    def addChild(self, device: "HubspaceRawDevice"):
        self.children.append(device)


class Hubspace:
    """Class to test interaction with Hubspace."""

    _refresh_token = None
    _password = None
    _username = None
    _accountId = None
    _last_token = None
    _last_token_time = None
    # Token lasts 120 seconds
    _token_duration = 118 * 1000

    # all the devices returned from the metadata array
    _raw_devices = []

    # all the devices categorized with children under them
    _devices: dict[str, HubspaceRawDevice] = {}

    def __init__(self, username, password) -> None:
        """Init the hubspace hub."""
        self._username = username
        self._password = password

    def authenticate(self) -> bool:
        """Test if we can authenticate with the host."""
        self._refresh_token = self.getRefreshCode()
        self._accountId = self.getAccountId()
        return self._refresh_token is not None and self._accountId is not None

    def getUTCTime(self):
        date = datetime.datetime.utcnow()
        utc_time = calendar.timegm(date.utctimetuple()) * 1000
        return utc_time

    def getCodeVerifierAndChallenge(self):
        code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode("utf-8")
        code_verifier = re.sub("[^a-zA-Z0-9]+", "", code_verifier)
        code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode("utf-8")
        code_challenge = code_challenge.replace("=", "")
        return code_challenge, code_verifier

    def getRefreshCode(self):
        URL = "https://accounts.hubspaceconnect.com/auth/realms/thd/protocol/openid-connect/auth"

        [code_challenge, code_verifier] = self.getCodeVerifierAndChallenge()

        # defining a params dict for the parameters to be sent to the API
        PARAMS = {
            "response_type": "code",
            "client_id": "hubspace_android",
            "redirect_uri": "hubspace-app://loginredirect",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "scope": "openid offline_access",
        }

        # sending get request and saving the response as response object
        r = requests.get(url=URL, params=PARAMS)
        r.close()
        headers = r.headers

        session_code = re.search("session_code=(.+?)&", r.text).group(1)
        execution = re.search("execution=(.+?)&", r.text).group(1)
        tab_id = re.search("tab_id=(.+?)&", r.text).group(1)

        auth_url = (
            "https://accounts.hubspaceconnect.com/auth/realms/thd/login-actions/authenticate?session_code="
            + session_code
            + "&execution="
            + execution
            + "&client_id=hubspace_android&tab_id="
            + tab_id
        )

        auth_header = {
            "Content-Type": "application/x-www-form-urlencoded",
            "user-agent": "Mozilla/5.0 (Linux; Android 7.1.1; Android SDK built for x86_64 Build/NYC) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36",
        }

        auth_data = {
            "username": self._username,
            "password": self._password,
            "credentialId": "",
        }

        r = requests.post(
            auth_url,
            data=auth_data,
            headers=auth_header,
            cookies=r.cookies.get_dict(),
            allow_redirects=False,
            timeout=TIMEOUT,
        )
        r.close()
        location = r.headers.get("location")

        session_state = re.search("session_state=(.+?)&code", location).group(1)
        code = re.search("&code=(.+?)$", location).group(1)

        auth_url = "https://accounts.hubspaceconnect.com/auth/realms/thd/protocol/openid-connect/token"

        auth_header = {
            "Content-Type": "application/x-www-form-urlencoded",
            "user-agent": "Dart/2.15 (dart:io)",
            "host": "accounts.hubspaceconnect.com",
        }

        auth_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "hubspace-app://loginredirect",
            "code_verifier": code_verifier,
            "client_id": "hubspace_android",
        }

        r = requests.post(
            auth_url, data=auth_data, headers=auth_header, timeout=TIMEOUT
        )
        r.close()
        refresh_token = r.json().get("refresh_token")
        # print(refresh_token)
        return refresh_token

    def getAuthTokenFromRefreshToken(self):
        utcTime = self.getUTCTime()

        if self._last_token is not None and (
            (utcTime - self._last_token_time) < self._token_duration
        ):
            _LOGGER.debug("Resuse Token")
            return self._last_token

        _LOGGER.debug("Get New Token")
        auth_url = "https://accounts.hubspaceconnect.com/auth/realms/thd/protocol/openid-connect/token"

        auth_header = {
            "Content-Type": "application/x-www-form-urlencoded",
            "user-agent": "Dart/2.15 (dart:io)",
            "host": "accounts.hubspaceconnect.com",
        }

        auth_data = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "scope": "openid email offline_access profile",
            "client_id": "hubspace_android",
        }

        r = requests.post(
            auth_url, data=auth_data, headers=auth_header, timeout=TIMEOUT
        )
        r.close()
        token = r.json().get("id_token")
        self._last_token = token
        self._last_token_time = utcTime

        return token

    def getAccountId(self):
        token = self.getAuthTokenFromRefreshToken()
        auth_url = "https://api2.afero.net/v1/users/me"

        auth_header = {
            "user-agent": "Dart/2.15 (dart:io)",
            "host": "api2.afero.net",
            "accept-encoding": "gzip",
            "authorization": "Bearer " + token,
        }

        auth_data = {}
        r = requests.get(auth_url, data=auth_data, headers=auth_header, timeout=TIMEOUT)
        r.close()
        accountId = r.json().get("accountAccess")[0].get("account").get("accountId")
        return accountId

    def getMetadeviceInfo(self):
        token = self.getAuthTokenFromRefreshToken()

        auth_header = {
            "user-agent": "Dart/2.15 (dart:io)",
            "host": "semantics2.afero.net",
            "accept-encoding": "gzip",
            "authorization": "Bearer " + token,
        }

        auth_url = (
            "https://api2.afero.net/v1/accounts/"
            + self._accountId
            + "/metadevices?expansions=state"
        )

        auth_data = {}
        r = requests.get(auth_url, data=auth_data, headers=auth_header, timeout=TIMEOUT)
        r.close()

        return r

    def discoverDeviceIds(self):
        response = self.getMetadeviceInfo()

        results = response.json()

        _devices: dict[str, HubspaceRawDevice] = {}

        # do 1 loop to get all the devices that have childen
        for lis in results:
            if (
                lis.get("typeId") == "metadevice.device"
                and len(lis.get("children", [])) != 0
            ):
                device = HubspaceRawDevice(
                    id=lis.get("id"),
                    deviceId=lis.get("deviceId"),
                    deviceClass=lis.get("description", {})
                    .get("device", {})
                    .get("deviceClass"),
                    model=lis.get("description", {}).get("device", {}).get("model"),
                    friendlyName=lis.get("friendlyName"),
                    functions=lis.get("description", {}).get("functions", []),
                    state=lis.get("state", {}).get("values", []),
                )
                _devices[device.deviceId] = device

        # loop again to get all the devices that do no have childen.
        for lis in results:
            if (
                lis.get("typeId") == "metadevice.device"
                and len(lis.get("children", [])) == 0
            ):
                deviceClass = (
                    lis.get("description", {}).get("device", {}).get("deviceClass")
                )
                functions = lis.get("description", {}).get("functions", [])
                deviceId = lis.get("deviceId")
                device = None

                # Some extra work because outlets are 2 seperate entities, but 1 device.
                if deviceClass == "power-outlet":
                    for function in functions:
                        if function.get("functionClass") == "toggle":
                            try:
                                _LOGGER.debug(
                                    f"Found toggle with id {function.get('id')} and instance {function.get('functionInstance')}"
                                )
                                outletIndex = function.get("functionInstance").split(
                                    "-"
                                )[1]
                                device = HubspaceRawDevice(
                                    id=lis.get("id"),
                                    deviceId=lis.get("deviceId"),
                                    deviceClass=deviceClass,
                                    model=lis.get("description", {})
                                    .get("device", {})
                                    .get("model"),
                                    friendlyName=lis.get("friendlyName"),
                                    functions=functions,
                                    state=lis.get("state", {}).get("values", []),
                                    outletIndex=outletIndex,
                                )
                                deviceId = f"{device.deviceId}_{outletIndex}"
                                _devices[deviceId] = device
                            except IndexError:
                                _LOGGER.debug("Error extracting outlet index")
                else:
                    device = HubspaceRawDevice(
                        id=lis.get("id"),
                        deviceId=deviceId,
                        deviceClass=deviceClass,
                        model=lis.get("description", {}).get("device", {}).get("model"),
                        friendlyName=lis.get("friendlyName"),
                        functions=functions,
                        state=lis.get("state", {}).get("values", []),
                    )
                    if deviceId in _devices:
                        _devices[deviceId].addChild(device=device)
                    else:
                        _devices[deviceId] = device
        self._devices = _devices

    @property
    def lights(self) -> dict[str, HubspaceRawDevice]:
        return {
            key: value
            for key, value in self._devices.items()
            if value.deviceClass == "light"
        }

    @property
    def ceilingFans(self) -> dict[str, HubspaceRawDevice]:
        return {
            key: value
            for key, value in self._devices.items()
            if value.deviceClass == "ceiling-fan"
        }

    @property
    def switches(self) -> dict[str, HubspaceRawDevice]:
        return {
            key: value
            for key, value in self._devices.items()
            if value.deviceClass in ("switch", "power-outlet")
        }