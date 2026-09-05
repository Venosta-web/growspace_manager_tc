"""The daily loop — the five Maintenance Actions, and the history they write.

One command per act, and no general "record an action" command taking a type.
The five acts do genuinely different things — one of them creates Cultures, two
end one, one changes a Stage, one only observes — so a single command would
either take a union of everything or validate nothing, and the card would have
to know which combination of fields belongs to which act anyway.  Five commands
put that knowledge where voluptuous can check it.

Every act replies with the whole board entry for the line, because a Replate
can divide one Culture into several and the smallest honest unit of change is
therefore the line, not the vessel the command named.  The recorded act travels
back beside it so the card can show what it just wrote without re-reading the
history.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from ..const import DOMAIN
from ..models.common import required_text
from ..models.maintenance import DiscardReason, MaintenanceAction, MaintenanceActionType
from ..storage_manager import StorageManager
from ._common import board_entry, tc_command

_LOGGER = logging.getLogger(__name__)
BRIDGE_TIMEOUT_SECONDS = 30

WS_TYPE_REPLATE = f"{DOMAIN}/maintenance/replate"
WS_TYPE_DISCARD = f"{DOMAIN}/maintenance/discard"
WS_TYPE_NOTE = f"{DOMAIN}/maintenance/note"
WS_TYPE_MOVE_TO_ROOTING = f"{DOMAIN}/maintenance/move_to_rooting"
WS_TYPE_GRADUATE = f"{DOMAIN}/maintenance/graduate"
WS_TYPE_MAINTENANCE_HISTORY = f"{DOMAIN}/maintenance/history"

# As everywhere in this namespace, the declarations stop at required-ness and
# gross type.  The vocabulary of reasons, the vessel count, a note longer than
# the store should hold — every one of those is a value the grower can fix, so
# it belongs to `models/maintenance.py` and comes back as `validation_failed`
# with a sentence rather than as a voluptuous dump.
_CULTURE: dict[Any, Any] = {vol.Required("culture_id"): str}
_NOTE: dict[Any, Any] = {vol.Optional("note"): vol.Any(str, None)}

SCHEMA_WS_REPLATE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_REPLATE,
        **_CULTURE,
        **_NOTE,
        vol.Required("medium_id"): str,
        vol.Required("medium_version"): int,
        vol.Required("vessels"): list,
    }
)

SCHEMA_WS_DISCARD = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_DISCARD,
        **_CULTURE,
        **_NOTE,
        vol.Required("reason"): str,
    }
)

SCHEMA_WS_NOTE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_NOTE,
        **_CULTURE,
        vol.Required("note"): str,
    }
)

SCHEMA_WS_MOVE_TO_ROOTING = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_MOVE_TO_ROOTING,
        **_CULTURE,
        **_NOTE,
    }
)

SCHEMA_WS_GRADUATE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_GRADUATE,
        **_CULTURE,
        **_NOTE,
        vol.Optional("plant"): {
            vol.Required("growspace_id"): str,
            vol.Required("strain"): str,
            vol.Optional("phenotype", default=""): str,
            vol.Required("row"): vol.All(int, vol.Range(min=1)),
            vol.Required("col"): vol.All(int, vol.Range(min=1)),
        },
    }
)

SCHEMA_WS_MAINTENANCE_HISTORY = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_MAINTENANCE_HISTORY,
        vol.Optional("culture_id"): str,
        vol.Optional("line_id"): str,
    }
)


def _recorded(storage: StorageManager, action: MaintenanceAction) -> dict[str, Any]:
    """Return the reply every act answers with: the line, and what was written."""
    return {
        "line": board_entry(storage, action.line_id),
        "action": action.to_dict(),
    }


@tc_command
async def websocket_replate(
    hass: HomeAssistant, storage: StorageManager, msg: dict[str, Any]
) -> dict[str, Any]:
    """Transfer a Culture onto fresh medium, optionally dividing it.

    The first vessel is the Culture that was replated and the rest are the
    division, so a plain transfer and a split are the same command with a
    longer list — the card has one dialog, and the history has one shape to
    read a multiplication rate out of.
    """
    action = storage.repository.replate_culture(
        msg["culture_id"],
        msg["medium_id"],
        msg["medium_version"],
        msg["vessels"],
        note=msg.get("note"),
    )
    await storage.async_save()
    return _recorded(storage, action)


@tc_command
async def websocket_discard(
    hass: HomeAssistant, storage: StorageManager, msg: dict[str, Any]
) -> dict[str, Any]:
    """End a Culture with a reason. The vessel stays on the board, ended."""
    action = storage.repository.discard_culture(
        msg["culture_id"], msg["reason"], note=msg.get("note")
    )
    await storage.async_save()
    return _recorded(storage, action)


@tc_command
async def websocket_note(
    hass: HomeAssistant, storage: StorageManager, msg: dict[str, Any]
) -> dict[str, Any]:
    """Record an observation against a Culture, changing nothing else."""
    action = storage.repository.note_on_culture(msg["culture_id"], msg["note"])
    await storage.async_save()
    return _recorded(storage, action)


@tc_command
async def websocket_move_to_rooting(
    hass: HomeAssistant, storage: StorageManager, msg: dict[str, Any]
) -> dict[str, Any]:
    """Move a Culture to the rooting Stage.

    Which changes its Replate Due Date without touching its anchor: the vessel
    is on the medium it was already on, and only the interval that applies to
    it has changed.
    """
    action = storage.repository.move_culture_to_rooting(
        msg["culture_id"], note=msg.get("note")
    )
    await storage.async_save()
    return _recorded(storage, action)


def _plant_id(response: dict[str, Any] | None) -> str:
    """Validate the optional public service response before completing the link."""
    return required_text(response.get("plant_id") if response else None, "Plant", 64)


@tc_command
async def websocket_graduate(
    hass: HomeAssistant, storage: StorageManager, msg: dict[str, Any]
) -> dict[str, Any]:
    """Persist the ending first, then optionally create one GM clone.

    Omission of `plant` is opt-out. GM alone validates the destination and
    genetics. Never decode TC's opaque phenotype reference or read GM internals.
    A failed or unsupported call leaves the saved plain graduation intact.
    """
    action = storage.repository.graduate_culture(
        msg["culture_id"], note=msg.get("note")
    )
    await storage.async_save()
    if "plant" in msg:
        try:
            async with asyncio.timeout(BRIDGE_TIMEOUT_SECONDS):
                response = await hass.services.async_call(
                    "growspace_manager",
                    "add_plant",
                    {**msg["plant"], "clone_start": action.recorded_at},
                    blocking=True,
                    return_response=True,
                )
            action = storage.repository.link_graduated_plant(
                action.id, _plant_id(response)
            )
        except Exception:
            # A remote operation can fail after creating a plant. Do not retry:
            # retain the ending and let the grower inspect GM before adding one.
            _LOGGER.exception(
                "Culture %s graduated without a linked plant",
                action.culture_id,
            )
        else:
            await storage.async_save()
    return _recorded(storage, action)


@tc_command
async def websocket_maintenance_history(
    hass: HomeAssistant, storage: StorageManager, msg: dict[str, Any]
) -> dict[str, Any]:
    """Return recorded acts, newest first.

    Filterable by Culture or by line and unfiltered otherwise, because those
    are the three questions: what happened to this vessel, what happened to
    this lineage, and what happened lately.  The history is append-only, so a
    reply is a fact about the past and never has to be reconciled with an
    earlier one.
    """
    return {
        "actions": [
            action.to_dict()
            for action in storage.repository.maintenance_actions(
                culture_id=msg.get("culture_id"), line_id=msg.get("line_id")
            )
        ]
    }


# The vocabularies are re-exported so the tests, the calendar and the card's
# contract fixture name them from one place rather than repeating the strings.
MAINTENANCE_ACTIONS: tuple[str, ...] = tuple(
    action.value for action in MaintenanceActionType
)
DISCARD_REASONS: tuple[str, ...] = tuple(reason.value for reason in DiscardReason)

COMMANDS: tuple[tuple[str, Any, vol.Schema], ...] = (
    (WS_TYPE_REPLATE, websocket_replate, SCHEMA_WS_REPLATE),
    (WS_TYPE_DISCARD, websocket_discard, SCHEMA_WS_DISCARD),
    (WS_TYPE_NOTE, websocket_note, SCHEMA_WS_NOTE),
    (WS_TYPE_MOVE_TO_ROOTING, websocket_move_to_rooting, SCHEMA_WS_MOVE_TO_ROOTING),
    (WS_TYPE_GRADUATE, websocket_graduate, SCHEMA_WS_GRADUATE),
    (
        WS_TYPE_MAINTENANCE_HISTORY,
        websocket_maintenance_history,
        SCHEMA_WS_MAINTENANCE_HISTORY,
    ),
)
