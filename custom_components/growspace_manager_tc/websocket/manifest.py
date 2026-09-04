"""The manifest command — what this integration is, and what it is holding.

This is the whole of the presence contract. The card cannot ask Home Assistant
whether a custom integration is installed, so it asks this namespace a question
instead: a reply means Growspace Manager TC is there and says which contract it
speaks, and any failure means there is no TC surface to render.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from ..const import DOMAIN, TC_CONTRACT_VERSION, WS_ERR_NOT_LOADED
from ..storage_manager import StorageManager

WS_TYPE_GET_MANIFEST = f"{DOMAIN}/get_manifest"
SCHEMA_WS_GET_MANIFEST = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_GET_MANIFEST,
    }
)

# The features this contract version can carry. V1's model tickets append to it
# as they land, and the card gates each surface on membership rather than on
# `integration_version` — an installed version is not the same claim as a
# working feature.
MANIFEST_FEATURES: list[str] = []


def _loaded_storage(hass: HomeAssistant) -> StorageManager | None:
    """Return the storage of the loaded entry, or None if there is none.

    Home Assistant offers no way to unregister a WebSocket command, so the
    namespace outlives the entry that registered it. Answering from
    `runtime_data` of a loaded entry is what keeps a removed integration
    indistinguishable — to the card — from one that was never installed.
    """
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            storage: StorageManager = entry.runtime_data
            return storage
    return None


async def async_build_manifest(
    hass: HomeAssistant, storage: StorageManager
) -> dict[str, Any]:
    """Build the manifest payload for a loaded entry."""
    integration = await async_get_integration(hass, DOMAIN)
    return {
        "contract_version": TC_CONTRACT_VERSION,
        "integration_version": str(integration.version),
        "features": list(MANIFEST_FEATURES),
        "collections": storage.repository.collection_sizes(),
    }


@websocket_api.async_response
async def websocket_get_manifest(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Answer with the contract this installation speaks, and what it holds."""
    storage = _loaded_storage(hass)
    if storage is None:
        connection.send_error(
            msg["id"],
            WS_ERR_NOT_LOADED,
            "Growspace Manager TC is installed but has no loaded config entry.",
        )
        return

    connection.send_result(msg["id"], await async_build_manifest(hass, storage))
