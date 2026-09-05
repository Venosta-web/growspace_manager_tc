"""Tests for the Maintenance Action commands and the history they write."""

from typing import Any
from unittest.mock import AsyncMock

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
    WS_TYPE_CREATE_CULTURE_MEDIUM,
    WS_TYPE_DISCARD,
    WS_TYPE_GRADUATE,
    WS_TYPE_INTRODUCE_CULTURE_LINE,
    WS_TYPE_MAINTENANCE_HISTORY,
    WS_TYPE_MOVE_TO_ROOTING,
    WS_TYPE_NOTE,
    WS_TYPE_REPLATE,
)
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError

AN_INTRODUCTION: dict[str, Any] = {
    "phenotype_id": "Blue Dream|Pheno 2",
    "phenotype_name": "Blue Dream — Pheno 2",
    "replate_interval_days": {"multiplication": 30, "rooting": 21},
    "plantlet_count": 6,
    "location": "Shelf A",
}
A_MEDIUM: dict[str, Any] = {
    "name": "MS + BAP 1.0",
    "base_salts": "MS full strength",
    "additives": [],
    "hormones": [{"name": "BAP", "amount": 1.0, "unit": "mg/L"}],
    "agar_g_per_l": 7.0,
    "sugar_g_per_l": 30.0,
    "ph_target": 5.8,
    "notes": "",
}


@pytest.fixture
async def entry(hass: HomeAssistant, growspace_manager_loaded: None) -> MockConfigEntry:
    """Return a loaded config entry."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


class Bench:
    """One line, its first vessel and one medium, plus a numbered client."""

    def __init__(self, client: Any) -> None:
        """Wrap a WebSocket client with an incrementing message ID."""
        self.client = client
        self._id = 0

    async def call(self, command: str, **payload: Any) -> dict[str, Any]:
        """Send one command and return its response."""
        self._id += 1
        await self.client.send_json({"id": self._id, "type": command, **payload})
        return await self.client.receive_json()

    async def ok(self, command: str, **payload: Any) -> dict[str, Any]:
        """Send one command that is expected to succeed."""
        response = await self.call(command, **payload)
        assert response["success"], response
        return response["result"]


@pytest.fixture
async def bench(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> Bench:
    """Return a bench with one medium, one line and one vessel already on it."""
    bench = Bench(await hass_ws_client(hass))
    medium = await bench.ok(WS_TYPE_CREATE_CULTURE_MEDIUM, **A_MEDIUM)
    line = await bench.ok(WS_TYPE_INTRODUCE_CULTURE_LINE, **AN_INTRODUCTION)
    bench.medium = medium["medium"]  # type: ignore[attr-defined]
    bench.line = line["line"]  # type: ignore[attr-defined]
    bench.culture = line["line"]["cultures"][0]  # type: ignore[attr-defined]
    return bench


async def _replate(bench: Bench, **overrides: Any) -> dict[str, Any]:
    """Replate the bench's vessel onto the bench's medium."""
    return await bench.ok(
        WS_TYPE_REPLATE,
        **{
            "culture_id": bench.culture["id"],  # type: ignore[attr-defined]
            "medium_id": bench.medium["id"],  # type: ignore[attr-defined]
            "medium_version": bench.medium["current_version"],  # type: ignore[attr-defined]
            "vessels": [{"plantlet_count": 5}],
            **overrides,
        },
    )


async def test_the_board_carries_a_replate_due_date(bench: Bench) -> None:
    """The worklist's whole input, computed from the line's interval."""
    culture = bench.culture  # type: ignore[attr-defined]

    assert culture["replate_due_at"] is not None
    assert culture["replate_due_at"] > culture["last_replated_at"]


async def test_a_replate_answers_with_the_line_and_the_act(bench: Bench) -> None:
    """The line, because a replate can divide; the act, so nothing re-reads history."""
    result = await _replate(bench)

    assert result["action"]["action"] == "replate"
    assert result["action"]["medium_id"] == bench.medium["id"]  # type: ignore[attr-defined]
    assert result["action"]["medium_version"] == 1
    assert len(result["line"]["cultures"]) == 1
    replated = result["line"]["cultures"][0]
    assert replated["id"] == bench.culture["id"]  # type: ignore[attr-defined]
    assert replated["plantlet_count"] == 5
    assert replated["replate_due_at"] > bench.culture["replate_due_at"]  # type: ignore[attr-defined]


async def test_a_replate_divides_one_vessel_into_several(bench: Bench) -> None:
    """One command, one dialog: a plain transfer is a division of one."""
    result = await _replate(
        bench,
        vessels=[
            {"plantlet_count": 5, "location": "Shelf A"},
            {"plantlet_count": 4, "location": "Shelf B"},
        ],
    )

    cultures = result["line"]["cultures"]
    assert len(cultures) == 2
    assert [vessel["culture_id"] for vessel in result["action"]["vessels"]] == [
        culture["id"] for culture in cultures
    ]
    assert cultures[1]["location"] == "Shelf B"
    assert cultures[1]["status"] == "active"


async def test_a_replate_survives_a_restart(
    bench: Bench, hass_storage: dict[str, Any]
) -> None:
    """The vessels and the act are both written."""
    result = await _replate(bench, vessels=[{}, {}])

    stored = hass_storage[STORAGE_KEY]["data"]
    assert len(stored["cultures"]) == 2
    assert stored["maintenance_actions"][result["action"]["id"]]["action"] == "replate"


async def test_a_discard_ends_the_vessel_and_keeps_it_on_the_board(
    bench: Bench,
) -> None:
    """History is kept: the vessel is ended, never removed."""
    result = await bench.ok(
        WS_TYPE_DISCARD,
        culture_id=bench.culture["id"],  # type: ignore[attr-defined]
        reason="contamination",
        note="Bacterial haze.",
    )

    culture = result["line"]["cultures"][0]
    assert culture["status"] == "discarded"
    assert culture["replate_due_at"] is None
    assert result["action"]["reason"] == "contamination"


async def test_a_note_records_an_observation_and_changes_nothing(
    bench: Bench,
) -> None:
    """The one act that leaves the vessel exactly as it was."""
    result = await bench.ok(
        WS_TYPE_NOTE,
        culture_id=bench.culture["id"],
        note="Slight vitrification.",  # type: ignore[attr-defined]
    )

    assert result["line"]["cultures"][0] == bench.culture  # type: ignore[attr-defined]
    assert result["action"]["note"] == "Slight vitrification."


async def test_moving_to_rooting_changes_the_stage_and_the_due_date(
    bench: Bench,
) -> None:
    """A shorter interval against the same anchor."""
    result = await bench.ok(
        WS_TYPE_MOVE_TO_ROOTING,
        culture_id=bench.culture["id"],  # type: ignore[attr-defined]
    )

    culture = result["line"]["cultures"][0]
    assert culture["stage"] == "rooting"
    assert culture["last_replated_at"] == bench.culture["last_replated_at"]  # type: ignore[attr-defined]
    assert culture["replate_due_at"] < bench.culture["replate_due_at"]  # type: ignore[attr-defined]
    assert result["action"]["stage"] == "rooting"


async def test_a_graduation_is_a_plain_ending(bench: Bench) -> None:
    """The Growspace Manager bridge is a later ticket; the end is recorded now."""
    result = await bench.ok(
        WS_TYPE_GRADUATE,
        culture_id=bench.culture["id"],
        note="Humidity dome.",  # type: ignore[attr-defined]
    )

    assert result["line"]["cultures"][0]["status"] == "graduated"
    assert result["action"]["action"] == "graduate"


async def test_the_history_is_newest_first_and_filterable(bench: Bench) -> None:
    """The three questions the append-only record set has to answer."""
    await _replate(bench)
    await bench.ok(WS_TYPE_NOTE, culture_id=bench.culture["id"], note="Looking good.")  # type: ignore[attr-defined]

    everything = await bench.ok(WS_TYPE_MAINTENANCE_HISTORY)
    assert [action["action"] for action in everything["actions"]] == ["note", "replate"]

    per_line = await bench.ok(
        WS_TYPE_MAINTENANCE_HISTORY,
        line_id=bench.line["id"],  # type: ignore[attr-defined]
    )
    assert len(per_line["actions"]) == 2

    elsewhere = await bench.ok(WS_TYPE_MAINTENANCE_HISTORY, culture_id="nobody")
    assert elsewhere["actions"] == []


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"vessels": []}, "at least one vessel"),
        ({"vessels": [{"plantlet_count": -2}]}, "Plantlet count"),
        ({"medium_version": 9}, "no version 9"),
    ],
)
async def test_a_value_the_grower_has_to_fix_is_named(
    bench: Bench, overrides: dict[str, Any], message: str
) -> None:
    """`validation_failed` with a sentence, never a voluptuous dump."""
    response = await bench.call(
        WS_TYPE_REPLATE,
        **{
            "culture_id": bench.culture["id"],  # type: ignore[attr-defined]
            "medium_id": bench.medium["id"],  # type: ignore[attr-defined]
            "medium_version": bench.medium["current_version"],  # type: ignore[attr-defined]
            "vessels": [{}],
            **overrides,
        },
    )

    assert not response["success"]
    assert response["error"]["code"] == WS_ERR_VALIDATION_FAILED
    assert message in response["error"]["message"]


async def test_a_wrong_type_is_a_card_bug(bench: Bench) -> None:
    """Voluptuous rejects the shape before any grower-facing rule runs."""
    response = await bench.call(
        WS_TYPE_REPLATE,
        culture_id=bench.culture["id"],  # type: ignore[attr-defined]
        medium_id=bench.medium["id"],  # type: ignore[attr-defined]
        medium_version="one",
        vessels=[{}],
    )

    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"


@pytest.mark.parametrize(
    ("command", "payload"),
    [
        (WS_TYPE_DISCARD, {"reason": "spent"}),
        (WS_TYPE_NOTE, {"note": "x"}),
        (WS_TYPE_MOVE_TO_ROOTING, {}),
        (WS_TYPE_GRADUATE, {}),
    ],
)
async def test_an_unknown_culture_is_not_found(
    bench: Bench, command: str, payload: dict[str, Any]
) -> None:
    """The card can tell a stale board from a broken backend."""
    response = await bench.call(command, culture_id="nope", **payload)

    assert not response["success"]
    assert response["error"]["code"] == WS_ERR_NOT_FOUND


async def test_an_ended_vessel_refuses_a_second_ending(bench: Bench) -> None:
    """A stale board cannot discard the same vessel twice."""
    await bench.ok(WS_TYPE_DISCARD, culture_id=bench.culture["id"], reason="spent")  # type: ignore[attr-defined]

    response = await bench.call(
        WS_TYPE_GRADUATE,
        culture_id=bench.culture["id"],  # type: ignore[attr-defined]
    )

    assert not response["success"]
    assert response["error"]["code"] == WS_ERR_VALIDATION_FAILED
    assert "already been discarded" in response["error"]["message"]


async def test_maintenance_refuses_when_no_entry_is_loaded(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """The namespace outlives the entry, and says so rather than answering."""
    client = await hass_ws_client(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await client.send_json({"id": 1, "type": WS_TYPE_MAINTENANCE_HISTORY})
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == WS_ERR_NOT_LOADED


PLANT_REQUEST = {
    "growspace_id": "tent",
    "strain": "Blue Dream",
    "phenotype": "Pheno 2",
    "row": 1,
    "col": 2,
}


async def test_graduation_creates_and_persists_link(
    hass: HomeAssistant,
    bench: Bench,
    hass_storage: dict[str, Any],
    entry: MockConfigEntry,
) -> None:
    """The real service registry receives one clone; reload preserves its ID."""
    calls = []

    async def add_plant(call: ServiceCall) -> dict[str, str]:
        calls.append(call)
        # TC is already durable when the external operation begins.
        stored = hass_storage[STORAGE_KEY]["data"]
        assert next(iter(stored["cultures"].values()))["status"] == "graduated"
        return {"plant_id": "created-plant"}

    hass.services.async_register(
        "growspace_manager",
        "add_plant",
        add_plant,
        supports_response=SupportsResponse.OPTIONAL,
    )
    result = await bench.ok(
        WS_TYPE_GRADUATE, culture_id=bench.culture["id"], plant=PLANT_REQUEST
    )
    assert result["action"]["plant_id"] == "created-plant"
    assert len(calls) == 1
    assert dict(calls[0].data) == {
        **PLANT_REQUEST,
        "clone_start": result["action"]["recorded_at"],
    }
    await entry.runtime_data.async_load()
    history = await bench.ok(WS_TYPE_MAINTENANCE_HISTORY)
    assert history["actions"][0]["plant_id"] == "created-plant"
    again = await bench.call(
        WS_TYPE_GRADUATE, culture_id=bench.culture["id"], plant=PLANT_REQUEST
    )
    assert not again["success"]
    assert len(calls) == 1


@pytest.mark.parametrize(
    "outcome", ["raises", "missing", "legacy", "invalid", "empty", "timeout"]
)
async def test_bridge_failure_keeps_the_graduation(
    hass: HomeAssistant,
    bench: Bench,
    hass_storage: dict[str, Any],
    outcome: str,
) -> None:
    """Unavailable, old, failing and malformed GM services never undo an ending."""

    async def add_plant(call: ServiceCall) -> dict[str, Any] | None:
        if outcome == "empty":
            return None
        if outcome == "raises":
            raise HomeAssistantError("No room")
        if outcome == "timeout":
            raise TimeoutError
        return {"plant_id": 42}

    if outcome != "missing":
        hass.services.async_register(
            "growspace_manager",
            "add_plant",
            add_plant,
            supports_response=SupportsResponse.NONE
            if outcome == "legacy"
            else SupportsResponse.OPTIONAL,
        )
    result = await bench.ok(
        WS_TYPE_GRADUATE, culture_id=bench.culture["id"], plant=PLANT_REQUEST
    )
    assert result["line"]["cultures"][0]["status"] == "graduated"
    assert result["action"]["plant_id"] is None
    stored = hass_storage[STORAGE_KEY]["data"]["maintenance_actions"]
    assert stored[result["action"]["id"]]["plant_id"] is None


async def test_opt_out_never_calls_gm(hass: HomeAssistant, bench: Bench) -> None:
    """Omitting the plant request preserves the original command behaviour."""
    call = AsyncMock(return_value={"plant_id": "should-not-exist"})
    hass.services.async_register(
        "growspace_manager",
        "add_plant",
        call,
        supports_response=SupportsResponse.OPTIONAL,
    )
    result = await bench.ok(WS_TYPE_GRADUATE, culture_id=bench.culture["id"])
    call.assert_not_called()
    assert result["action"]["plant_id"] is None


async def test_invalid_graduation_note_does_not_end_culture(bench: Bench) -> None:
    """Local validation happens before committing the ending or calling GM."""
    result = await bench.call(
        WS_TYPE_GRADUATE, culture_id=bench.culture["id"], note="x" * 2001
    )
    assert not result["success"]
    result = await bench.ok(WS_TYPE_GRADUATE, culture_id=bench.culture["id"])
    assert result["action"]["action"] == "graduate"
