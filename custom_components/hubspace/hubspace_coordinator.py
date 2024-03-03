import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .hubspace_client import HubspaceClient

_LOGGER = logging.getLogger(__name__)


class HubspaceCoordinator(DataUpdateCoordinator):
    """Coordinates data between Hubspae and Homeassistant."""

    hubspace_client: HubspaceClient
    hass: HomeAssistant
    data: dict[str, Any]

    def __init__(self, hass: HomeAssistant, hubspace_client: HubspaceClient):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Hubspace Coordinator",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=30),
        )
        self.hubspace_client = hubspace_client
        self.hass = hass

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with asyncio.timeout(10):
                return await self.hass.async_add_executor_job(
                    self.hubspace_client.pull_coordinator_data
                )
        except any as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    @property
    def lights(self) -> list[str]:
        return [
            deviceId
            for [deviceId, device] in self.data.items()
            if device.get("description", {}).get("device", {}).get("deviceClass", None)
            == "light"
        ]

    @property
    def fans(self) -> list[str]:
        return [
            deviceId
            for [deviceId, device] in self.data.items()
            if device.get("description", {}).get("device", {}).get("deviceClass", None)
            == "fan"
        ]

    @property
    def switches(self) -> list[str]:
        return [
            deviceId
            for [deviceId, device] in self.data.items()
            if device.get("description", {}).get("device", {}).get("deviceClass", None)
            in ("switch", "power-outlet")
        ]