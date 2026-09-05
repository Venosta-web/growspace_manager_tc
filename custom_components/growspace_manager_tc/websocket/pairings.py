"""CRUD for the one curated pairing set."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from ..const import DOMAIN
from ..storage_manager import StorageManager
from ._common import tc_command

_FIELDS = {
    vol.Required("phenotype_id"): str,
    vol.Required("phenotype_name"): str,
    vol.Required("medium_id"): str,
    vol.Optional("notes"): str,
}


@tc_command
async def websocket_list_pairings(
    hass: HomeAssistant, storage: StorageManager, msg: dict[str, Any]
) -> dict[str, Any]:
    """Return endorsements, independent of Culture Medium versions."""
    return {"pairings": [row.to_dict() for row in storage.repository.pairings()]}


@tc_command
async def websocket_save_pairing(
    hass: HomeAssistant, storage: StorageManager, msg: dict[str, Any]
) -> dict[str, Any]:
    """Create or update an endorsement and persist it."""
    pairing = storage.repository.save_pairing(msg, pairing_id=msg.get("pairing_id"))
    await storage.async_save()
    return {"pairing": pairing.to_dict()}


@tc_command
async def websocket_delete_pairing(
    hass: HomeAssistant, storage: StorageManager, msg: dict[str, Any]
) -> dict[str, Any]:
    """Delete an endorsement and persist the remaining set."""
    pairing = storage.repository.delete_pairing(msg["pairing_id"])
    await storage.async_save()
    return {"pairing_id": pairing.id}


def _schema(action: str, fields: dict[Any, Any]) -> vol.Schema:
    """Build a command schema with the shared namespace."""
    return websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
        {vol.Required("type"): f"{DOMAIN}/pairings/{action}", **fields}
    )


COMMANDS: tuple[tuple[str, Any, vol.Schema], ...] = (
    (f"{DOMAIN}/pairings/list", websocket_list_pairings, _schema("list", {})),
    (f"{DOMAIN}/pairings/create", websocket_save_pairing, _schema("create", _FIELDS)),
    (
        f"{DOMAIN}/pairings/update",
        websocket_save_pairing,
        _schema("update", {**_FIELDS, vol.Required("pairing_id"): str}),
    ),
    (
        f"{DOMAIN}/pairings/delete",
        websocket_delete_pairing,
        _schema("delete", {vol.Required("pairing_id"): str}),
    ),
)
