"""The Hubspace integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .hubspace import Hubspace

PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hubspace from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    hub = Hubspace(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    authed = await hass.async_add_executor_job(hub.authenticate)
    if not authed:
        return False
    await hass.async_add_executor_job(hub.discoverDeviceIds)
    hass.data[DOMAIN][entry.entry_id] = hub

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
