"""The Hubspace integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .hubspace_client import HubspaceClient
from .hubspace_coordinator import HubspaceCoordinator

PLATFORMS: list[Platform] = [Platform.FAN]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hubspace from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    hubspace_client = HubspaceClient(
        entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
    )
    authed = await hass.async_add_executor_job(hubspace_client.authenticate)
    if not authed:
        return False
    coordinator = HubspaceCoordinator(hass, hubspace_client=hubspace_client)

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
