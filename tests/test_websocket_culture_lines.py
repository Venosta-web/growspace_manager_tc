"""Tests for the culture board commands."""

from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.growspace_manager_tc.const import (
    DOMAIN,
    STORAGE_KEY,
    WS_ERR_NOT_FOUND,
    WS_ERR_NOT_LOADED,
    WS_ERR_VALIDATION_FAILED,
)
from custom_components.growspace_manager_tc.websocket import (
    WS_TYPE_INTRODUCE_CULTURE_LINE,
    WS_TYPE_LIST_CULTURE_LINES,
    WS_TYPE_RELINK_PHENOTYPE,
    WS_TYPE_SET_CULTURE_LINE_ARCHIVED,
)
from homeassistant.core import HomeAssistant

AN_INTRODUCTION: dict[str, Any] = {
    "phenotype_id": "Blue Dream|Pheno 2",
    "phenotype_name": "Blue Dream — Pheno 2",
    "replate_interval_days": {"multiplication": 30, "rooting": 21},
    "plantlet_count": 6,
    "location": "Shelf A",
}


@pytest.fixture
async def entry(hass: HomeAssistant, growspace_manager_loaded: None) -> MockConfigEntry:
    """Return a loaded config entry."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _call(
    client: Any, message_id: int, command: str, **payload: Any
) -> dict[str, Any]:
    """Send one command and return its response."""
    await client.send_json({"id": message_id, "type": command, **payload})
    return await client.receive_json()


async def _introduce(client: Any, message_id: int, **overrides: Any) -> dict[str, Any]:
    """Perform an Introduction and return the line it produced."""
    response = await _call(
        client,
        message_id,
        WS_TYPE_INTRODUCE_CULTURE_LINE,
        **{**AN_INTRODUCTION, **overrides},
    )
    assert response["success"], response
    return response["result"]["line"]


async def test_the_board_starts_empty(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """A fresh install answers with a board, not an error."""
    client = await hass_ws_client(hass)

    response = await _call(client, 1, WS_TYPE_LIST_CULTURE_LINES)

    assert response["success"]
    assert response["result"] == {"culture_lines": []}


async def test_an_introduction_returns_the_line_with_its_first_culture(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """The reply is the whole board entry, so the card need not re-list."""
    client = await hass_ws_client(hass)

    line = await _introduce(client, 1)

    assert line["phenotype"]["id"] == "Blue Dream|Pheno 2"
    assert line["phenotype"]["name_snapshot"] == "Blue Dream — Pheno 2"
    assert line["replate_interval_days"] == {"multiplication": 30, "rooting": 21}
    assert line["archived_at"] is None
    assert len(line["cultures"]) == 1
    culture = line["cultures"][0]
    assert culture["line_id"] == line["id"]
    assert culture["status"] == "active"
    assert culture["stage"] == "multiplication"
    assert culture["plantlet_count"] == 6
    assert culture["location"] == "Shelf A"


async def test_an_introduction_survives_a_restart(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Both records are written, and the board reads back the same."""
    client = await hass_ws_client(hass)
    line = await _introduce(client, 1)

    stored = hass_storage[STORAGE_KEY]["data"]
    assert line["id"] in stored["culture_lines"]
    assert stored["cultures"][line["cultures"][0]["id"]]["line_id"] == line["id"]

    response = await _call(client, 2, WS_TYPE_LIST_CULTURE_LINES)
    assert response["result"]["culture_lines"] == [line]


async def test_the_board_lists_live_lines_before_archived_ones(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Ordering is the backend's, and archived lines are listed rather than dropped."""
    client = await hass_ws_client(hass)
    first = await _introduce(client, 1, phenotype_id="a|1", phenotype_name="Aaa")
    second = await _introduce(client, 2, phenotype_id="z|1", phenotype_name="Zzz")

    await _call(
        client, 3, WS_TYPE_SET_CULTURE_LINE_ARCHIVED, line_id=first["id"], archived=True
    )
    response = await _call(client, 4, WS_TYPE_LIST_CULTURE_LINES)

    assert [line["id"] for line in response["result"]["culture_lines"]] == [
        second["id"],
        first["id"],
    ]


async def test_relinking_replaces_the_reference_and_keeps_the_cultures(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """The way out of a Missing Phenotype that keeps the lineage."""
    client = await hass_ws_client(hass)
    line = await _introduce(client, 1)

    response = await _call(
        client,
        2,
        WS_TYPE_RELINK_PHENOTYPE,
        line_id=line["id"],
        phenotype_id="Gelato 33|Cut B",
        phenotype_name="Gelato 33 — Cut B",
    )

    assert response["success"]
    relinked = response["result"]["line"]
    assert relinked["phenotype"]["id"] == "Gelato 33|Cut B"
    assert relinked["phenotype"]["name_snapshot"] == "Gelato 33 — Cut B"
    assert relinked["cultures"] == line["cultures"]


async def test_archiving_stamps_and_is_reversible(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """The other way out, and it can be taken back."""
    client = await hass_ws_client(hass)
    line = await _introduce(client, 1)

    archived = await _call(
        client, 2, WS_TYPE_SET_CULTURE_LINE_ARCHIVED, line_id=line["id"], archived=True
    )
    assert archived["result"]["line"]["archived_at"] is not None

    restored = await _call(
        client, 3, WS_TYPE_SET_CULTURE_LINE_ARCHIVED, line_id=line["id"], archived=False
    )
    assert restored["result"]["line"]["archived_at"] is None


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"phenotype_name": "  "}, "Phenotype name"),
        ({"replate_interval_days": {"multiplication": 30}}, "Rooting interval"),
        ({"replate_interval_days": {"multiplication": 0, "rooting": 21}}, "between"),
        ({"stage": "callus"}, "multiplication, rooting"),
    ],
)
async def test_a_value_the_grower_has_to_fix_is_named(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    overrides: dict[str, Any],
    message: str,
) -> None:
    """`validation_failed` with a sentence, never a voluptuous dump."""
    client = await hass_ws_client(hass)

    response = await _call(
        client, 1, WS_TYPE_INTRODUCE_CULTURE_LINE, **{**AN_INTRODUCTION, **overrides}
    )

    assert not response["success"]
    assert response["error"]["code"] == WS_ERR_VALIDATION_FAILED
    assert message in response["error"]["message"]


async def test_a_wrong_type_is_a_card_bug(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Voluptuous rejects the shape before any grower-facing rule runs."""
    client = await hass_ws_client(hass)

    response = await _call(
        client,
        1,
        WS_TYPE_INTRODUCE_CULTURE_LINE,
        **{**AN_INTRODUCTION, "replate_interval_days": "30 days"},
    )

    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"


@pytest.mark.parametrize(
    ("command", "payload"),
    [
        (
            WS_TYPE_RELINK_PHENOTYPE,
            {"phenotype_id": "x|1", "phenotype_name": "X"},
        ),
        (WS_TYPE_SET_CULTURE_LINE_ARCHIVED, {"archived": True}),
    ],
)
async def test_an_unknown_line_is_not_found(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    command: str,
    payload: dict[str, Any],
) -> None:
    """The card can tell a stale board from a broken backend."""
    client = await hass_ws_client(hass)

    response = await _call(client, 1, command, line_id="nope", **payload)

    assert not response["success"]
    assert response["error"]["code"] == WS_ERR_NOT_FOUND


async def test_the_board_refuses_when_no_entry_is_loaded(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """The namespace outlives the entry, and says so rather than answering."""
    client = await hass_ws_client(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    response = await _call(client, 1, WS_TYPE_LIST_CULTURE_LINES)

    assert not response["success"]
    assert response["error"]["code"] == WS_ERR_NOT_LOADED
