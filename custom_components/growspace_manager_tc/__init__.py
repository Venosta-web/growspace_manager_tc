"""The Growspace Manager TC integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, GROWSPACE_MANAGER_DOMAIN
from .storage_manager import StorageManager
from .websocket import async_register_commands

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# The calendar is the integration's only entity: one per entry, carrying the
# Replate Due Dates. Everything else this integration serves is a WebSocket
# command, because the card is the surface and an entity per Culture would put
# a grower's whole bench into the state machine for nothing.
PLATFORMS: list[Platform] = [Platform.CALENDAR]

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover
    from typing import TypeAlias

GrowspaceTcConfigEntry: TypeAlias = ConfigEntry[StorageManager]  # noqa: UP040


async def async_setup_entry(hass: HomeAssistant, entry: GrowspaceTcConfigEntry) -> bool:
    """Set up Growspace Manager TC from a config entry.

    The config flow already refused to create an entry without Growspace
    Manager, but an entry outlives the integration that justified it — it is
    restored on every restart, and Growspace Manager can be removed or fail its
    own setup in the meantime.  Retry rather than fail permanently: the
    companion may still be on its way up.
    """
    if GROWSPACE_MANAGER_DOMAIN not in hass.config.components:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="growspace_manager_missing",
        )

    storage = StorageManager(hass)
    await storage.async_load()
    entry.runtime_data = storage

    # The namespace is registered here rather than in `async_setup` so that it
    # exists exactly when an entry does: the card reads its absence as "TC is
    # not installed", and Home Assistant only loads this integration at all
    # once an entry exists.
    async_register_commands(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("Growspace Manager TC set up for entry %s", entry.entry_id)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GrowspaceTcConfigEntry
) -> bool:
    """Unload a config entry.

    The calendar goes with the entry; the storage manager holds nothing beyond
    the loaded records, which go with it too.

    The WebSocket namespace is deliberately left registered — Home Assistant
    cannot unregister a command — and each handler refuses on its own once no
    entry is loaded.
    """
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
