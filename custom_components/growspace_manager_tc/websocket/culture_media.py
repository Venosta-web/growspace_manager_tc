"""The Culture Medium library — CRUD over the TC namespace.

Four commands over one collection, and one rule worth stating where the wire
shape is decided: `update` never rewrites a Medium Version.  It forks a new one
when the formulation changed and leaves the history alone when it did not, so
every version the card lists is a formulation that was really used and every
Plating that pins one still describes what was poured (ADR-0004).
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from ..const import DOMAIN
from ..models.culture_medium import MediumFormulation, validate_medium_name
from ..storage_manager import StorageManager
from ._common import tc_command

WS_TYPE_LIST_CULTURE_MEDIA = f"{DOMAIN}/culture_media/list"
WS_TYPE_CREATE_CULTURE_MEDIUM = f"{DOMAIN}/culture_media/create"
WS_TYPE_UPDATE_CULTURE_MEDIUM = f"{DOMAIN}/culture_media/update"
WS_TYPE_DELETE_CULTURE_MEDIUM = f"{DOMAIN}/culture_media/delete"

# The formulation travels flat, exactly as a Medium Version is rendered back —
# one shape for the form, the reply and the stored snapshot.
#
# These declarations stop at required-ness and gross type; every value rule
# (trimming, emptiness, ranges, duplicate component names) belongs to
# `models/culture_medium.py`, which can be argued with in a test that needs no
# Home Assistant.  The split is also what the card sees: a value the grower
# typed comes back as `validation_failed` with a sentence, while a wrong type is
# a card bug and comes back as voluptuous' `invalid_format`.
_NUMBER = vol.Any(int, float)
_FORMULATION_FIELDS = {
    vol.Required("base_salts"): str,
    vol.Optional("additives"): list,
    vol.Optional("hormones"): list,
    vol.Required("agar_g_per_l"): _NUMBER,
    vol.Required("sugar_g_per_l"): _NUMBER,
    vol.Required("ph_target"): _NUMBER,
    vol.Optional("notes"): str,
}

SCHEMA_WS_LIST_CULTURE_MEDIA = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_LIST_CULTURE_MEDIA,
    }
)

SCHEMA_WS_CREATE_CULTURE_MEDIUM = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_CREATE_CULTURE_MEDIUM,
        vol.Required("name"): str,
        **_FORMULATION_FIELDS,
    }
)

SCHEMA_WS_UPDATE_CULTURE_MEDIUM = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_UPDATE_CULTURE_MEDIUM,
        vol.Required("medium_id"): str,
        vol.Required("name"): str,
        **_FORMULATION_FIELDS,
    }
)

SCHEMA_WS_DELETE_CULTURE_MEDIUM = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_DELETE_CULTURE_MEDIUM,
        vol.Required("medium_id"): str,
    }
)


@tc_command
async def websocket_list_culture_media(
    hass: HomeAssistant, storage: StorageManager, msg: dict[str, Any]
) -> dict[str, Any]:
    """Return the whole library, every medium with its full version history.

    History is sent with the list rather than fetched per medium: a library is
    tens of records, and the card's whole job here is to show that editing forks
    rather than rewrites.
    """
    return {
        "culture_media": [
            medium.to_dict() for medium in storage.repository.culture_media()
        ]
    }


@tc_command
async def websocket_create_culture_medium(
    hass: HomeAssistant, storage: StorageManager, msg: dict[str, Any]
) -> dict[str, Any]:
    """Add a Culture Medium to the library at version 1."""
    medium = storage.repository.create_culture_medium(
        validate_medium_name(msg["name"]), MediumFormulation.from_payload(msg)
    )
    await storage.async_save()
    return {"medium": medium.to_dict()}


@tc_command
async def websocket_update_culture_medium(
    hass: HomeAssistant, storage: StorageManager, msg: dict[str, Any]
) -> dict[str, Any]:
    """Apply an edit, forking a Medium Version if the formulation changed."""
    medium = storage.repository.update_culture_medium(
        msg["medium_id"],
        validate_medium_name(msg["name"]),
        MediumFormulation.from_payload(msg),
    )
    await storage.async_save()
    return {"medium": medium.to_dict()}


@tc_command
async def websocket_delete_culture_medium(
    hass: HomeAssistant, storage: StorageManager, msg: dict[str, Any]
) -> dict[str, Any]:
    """Remove a Culture Medium, and with it its version history."""
    medium = storage.repository.delete_culture_medium(msg["medium_id"])
    await storage.async_save()
    return {"medium_id": medium.id}


COMMANDS: tuple[tuple[str, Any, vol.Schema], ...] = (
    (
        WS_TYPE_LIST_CULTURE_MEDIA,
        websocket_list_culture_media,
        SCHEMA_WS_LIST_CULTURE_MEDIA,
    ),
    (
        WS_TYPE_CREATE_CULTURE_MEDIUM,
        websocket_create_culture_medium,
        SCHEMA_WS_CREATE_CULTURE_MEDIUM,
    ),
    (
        WS_TYPE_UPDATE_CULTURE_MEDIUM,
        websocket_update_culture_medium,
        SCHEMA_WS_UPDATE_CULTURE_MEDIUM,
    ),
    (
        WS_TYPE_DELETE_CULTURE_MEDIUM,
        websocket_delete_culture_medium,
        SCHEMA_WS_DELETE_CULTURE_MEDIUM,
    ),
)
