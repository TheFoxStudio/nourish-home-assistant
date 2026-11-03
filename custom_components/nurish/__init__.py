"""Nourish food and water tracking integration."""

from homeassistant.const import Platform, CONF_URL, CONF_API_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .api import NourishApi
from .const import DOMAIN
from .coordinator import NourishCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass, entry):
    """Set up a Nourish account."""
    api = NourishApi(
        async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_API_TOKEN]
    )
    coordinator = NourishCoordinator(hass, entry, api)
    await coordinator.async_load()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass, entry):
    """Apply changed polling settings."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    """Unload the integration."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass, entry):
    """Remove the local private snapshot; Recorder history remains user-managed."""
    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}").async_remove()
