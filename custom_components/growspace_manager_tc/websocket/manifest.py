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
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from ..const import DOMAIN, FEATURE_CULTURE_MEDIA, TC_CONTRACT_VERSION
from ..storage_manager import StorageManager
from ._common import tc_command

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
MANIFEST_FEATURES: list[str] = [FEATURE_CULTURE_MEDIA]


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


@tc_command
async def websocket_get_manifest(
    hass: HomeAssistant, storage: StorageManager, msg: dict[str, Any]
) -> dict[str, Any]:
    """Answer with the contract this installation speaks, and what it holds."""
    return await async_build_manifest(hass, storage)
