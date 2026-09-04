"""The culture board — Culture Lines, their Cultures, and the Introduction.

Four commands over two collections, and one rule worth stating where the wire
shape is decided: **a line carries a phenotype ID and a name snapshot, and
nothing here resolves either.**  Growspace Manager owns phenotype identity
(ADR-0002); this integration would have to reach into another integration's
storage to look one up, which is the coupling the whole design exists to avoid.
So the card does the join client-side, and the snapshot is what it falls back
to when the ID no longer resolves (ADR-0006) — which is also why re-linking and
archiving are commands here rather than a card-side gesture.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from ..const import DOMAIN
from ..models.culture_line import CultureStage, PhenotypeReference, ReplateIntervals
from ..storage_manager import StorageManager
from ._common import tc_command

WS_TYPE_LIST_CULTURE_LINES = f"{DOMAIN}/culture_lines/list"
WS_TYPE_INTRODUCE_CULTURE_LINE = f"{DOMAIN}/culture_lines/introduce"
WS_TYPE_RELINK_PHENOTYPE = f"{DOMAIN}/culture_lines/relink_phenotype"
WS_TYPE_SET_CULTURE_LINE_ARCHIVED = f"{DOMAIN}/culture_lines/set_archived"

# As in the medium commands, these declarations stop at required-ness and gross
# type.  Every value rule — the stage vocabulary, the interval range, a blank
# phenotype name — belongs to `models/culture_line.py`, so a value the grower
# typed comes back as `validation_failed` with a sentence while a wrong type is
# a card bug and comes back as voluptuous' `invalid_format`.
_PHENOTYPE_FIELDS: dict[Any, Any] = {
    vol.Required("phenotype_id"): str,
    vol.Required("phenotype_name"): str,
}

SCHEMA_WS_LIST_CULTURE_LINES = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_LIST_CULTURE_LINES,
    }
)

SCHEMA_WS_INTRODUCE_CULTURE_LINE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_INTRODUCE_CULTURE_LINE,
        **_PHENOTYPE_FIELDS,
        vol.Required("replate_interval_days"): dict,
        vol.Optional("stage"): str,
        vol.Optional("plantlet_count"): vol.Any(int, None),
        vol.Optional("location"): str,
    }
)

SCHEMA_WS_RELINK_PHENOTYPE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_RELINK_PHENOTYPE,
        vol.Required("line_id"): str,
        **_PHENOTYPE_FIELDS,
    }
)

SCHEMA_WS_SET_CULTURE_LINE_ARCHIVED = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_SET_CULTURE_LINE_ARCHIVED,
        vol.Required("line_id"): str,
        vol.Required("archived"): bool,
    }
)


def _board_entry(storage: StorageManager, line_id: str) -> dict[str, Any]:
    """Return one line with its Cultures, the way the board reads it."""
    repository = storage.repository
    line = repository.culture_line(line_id)
    return line.to_payload(repository.cultures_of(line_id))


@tc_command
async def websocket_list_culture_lines(
    hass: HomeAssistant, storage: StorageManager, msg: dict[str, Any]
) -> dict[str, Any]:
    """Return every line with its Cultures.

    Cultures travel with their lines rather than behind a second call: the board
    is the whole surface, a collection is tens of records, and a card that had
    to fan out per line would render an empty board first and fill it in.
    Archived lines are included — the card decides whether to show them, and a
    line that vanished from the list would be indistinguishable from one that
    was deleted, which nothing here ever does.
    """
    repository = storage.repository
    return {
        "culture_lines": [
            line.to_payload(repository.cultures_of(line.id))
            for line in repository.culture_lines()
        ]
    }


@tc_command
async def websocket_introduce_culture_line(
    hass: HomeAssistant, storage: StorageManager, msg: dict[str, Any]
) -> dict[str, Any]:
    """Perform an Introduction: one line, its intervals, and its first Culture.

    The reply carries the finished line with its first vessel already in it, so
    the card updates the board from the answer rather than re-listing.
    """
    line, _culture = storage.repository.introduce_culture_line(
        PhenotypeReference.taken(msg["phenotype_id"], msg["phenotype_name"]),
        ReplateIntervals.from_payload(msg["replate_interval_days"]),
        stage=msg.get("stage"),
        plantlet_count=msg.get("plantlet_count"),
        location=msg.get("location"),
    )
    await storage.async_save()
    return {"line": _board_entry(storage, line.id)}


@tc_command
async def websocket_relink_phenotype(
    hass: HomeAssistant, storage: StorageManager, msg: dict[str, Any]
) -> dict[str, Any]:
    """Point a line at another phenotype, snapshotting its name afresh."""
    line = storage.repository.relink_phenotype(
        msg["line_id"],
        PhenotypeReference.taken(msg["phenotype_id"], msg["phenotype_name"]),
    )
    await storage.async_save()
    return {"line": _board_entry(storage, line.id)}


@tc_command
async def websocket_set_culture_line_archived(
    hass: HomeAssistant, storage: StorageManager, msg: dict[str, Any]
) -> dict[str, Any]:
    """Put a line away, or bring it back. Nothing is deleted either way."""
    line = storage.repository.set_culture_line_archived(msg["line_id"], msg["archived"])
    await storage.async_save()
    return {"line": _board_entry(storage, line.id)}


# The stage vocabulary is re-exported so the card's contract fixture and the
# tests name it from one place rather than repeating the two strings.
CULTURE_STAGES: tuple[str, ...] = tuple(stage.value for stage in CultureStage)

COMMANDS: tuple[tuple[str, Any, vol.Schema], ...] = (
    (
        WS_TYPE_LIST_CULTURE_LINES,
        websocket_list_culture_lines,
        SCHEMA_WS_LIST_CULTURE_LINES,
    ),
    (
        WS_TYPE_INTRODUCE_CULTURE_LINE,
        websocket_introduce_culture_line,
        SCHEMA_WS_INTRODUCE_CULTURE_LINE,
    ),
    (
        WS_TYPE_RELINK_PHENOTYPE,
        websocket_relink_phenotype,
        SCHEMA_WS_RELINK_PHENOTYPE,
    ),
    (
        WS_TYPE_SET_CULTURE_LINE_ARCHIVED,
        websocket_set_culture_line_archived,
        SCHEMA_WS_SET_CULTURE_LINE_ARCHIVED,
    ),
)
