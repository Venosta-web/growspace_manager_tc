"""Tests for the Culture Medium library commands."""

from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.growspace_manager_tc.const import (
    DOMAIN,
    STORAGE_KEY,
    WS_ERR_CONFLICT,
    WS_ERR_NOT_FOUND,
    WS_ERR_NOT_LOADED,
    WS_ERR_VALIDATION_FAILED,
)
from custom_components.growspace_manager_tc.websocket import (
    WS_TYPE_CREATE_CULTURE_MEDIUM,
    WS_TYPE_DELETE_CULTURE_MEDIUM,
    WS_TYPE_LIST_CULTURE_MEDIA,
    WS_TYPE_UPDATE_CULTURE_MEDIUM,
)
from homeassistant.core import HomeAssistant

A_MEDIUM: dict[str, Any] = {
    "name": "MS multiplication",
    "base_salts": "MS",
    "additives": [{"name": "myo-inositol", "amount": 100, "unit": "mg/L"}],
    "hormones": [{"name": "BAP", "amount": 1.0, "unit": "mg/L"}],
    "agar_g_per_l": 7.0,
    "sugar_g_per_l": 30.0,
    "ph_target": 5.8,
    "notes": "Autoclave 15 min.",
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


async def test_the_library_starts_empty(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """A fresh install answers with a library, not an error."""
    client = await hass_ws_client(hass)

    response = await _call(client, 1, WS_TYPE_LIST_CULTURE_MEDIA)

    assert response["success"]
    assert response["result"] == {"culture_media": []}


async def test_creating_a_medium_returns_it_at_version_one(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """The reply carries the whole medium, so the card need not re-list."""
    client = await hass_ws_client(hass)

    response = await _call(client, 1, WS_TYPE_CREATE_CULTURE_MEDIUM, **A_MEDIUM)

    assert response["success"]
    medium = response["result"]["medium"]
    assert medium["name"] == "MS multiplication"
    assert medium["current_version"] == 1
    assert len(medium["versions"]) == 1
    assert medium["versions"][0]["hormones"] == [
        {"name": "BAP", "amount": 1.0, "unit": "mg/L"}
    ]


async def test_a_created_medium_is_persisted(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    hass_storage: dict[str, Any],
    hass_ws_client: WebSocketGenerator,
) -> None:
    """The library outlives the connection that wrote to it."""
    client = await hass_ws_client(hass)

    response = await _call(client, 1, WS_TYPE_CREATE_CULTURE_MEDIUM, **A_MEDIUM)
    await hass.async_block_till_done()

    medium_id = response["result"]["medium"]["id"]
    stored = hass_storage[STORAGE_KEY]["data"]["culture_media"]
    assert stored[medium_id]["name"] == "MS multiplication"


async def test_editing_forks_a_version_and_leaves_the_prior_one(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """The point of the whole ticket, over the wire (ADR-0004)."""
    client = await hass_ws_client(hass)
    created = await _call(client, 1, WS_TYPE_CREATE_CULTURE_MEDIUM, **A_MEDIUM)
    medium_id = created["result"]["medium"]["id"]

    response = await _call(
        client,
        2,
        WS_TYPE_UPDATE_CULTURE_MEDIUM,
        medium_id=medium_id,
        **{**A_MEDIUM, "ph_target": 5.6},
    )

    assert response["success"]
    versions = response["result"]["medium"]["versions"]
    assert [version["version"] for version in versions] == [1, 2]
    assert versions[0]["ph_target"] == 5.8
    assert versions[1]["ph_target"] == 5.6
    assert response["result"]["medium"]["current_version"] == 2


async def test_renaming_does_not_fork_a_version(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """A version records a formulation, and a rename changes none."""
    client = await hass_ws_client(hass)
    created = await _call(client, 1, WS_TYPE_CREATE_CULTURE_MEDIUM, **A_MEDIUM)
    medium_id = created["result"]["medium"]["id"]

    response = await _call(
        client,
        2,
        WS_TYPE_UPDATE_CULTURE_MEDIUM,
        medium_id=medium_id,
        **{**A_MEDIUM, "name": "MS multi"},
    )

    assert response["success"]
    assert response["result"]["medium"]["name"] == "MS multi"
    assert len(response["result"]["medium"]["versions"]) == 1


async def test_the_list_carries_every_version(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """History is readable from the library call, not a second round trip."""
    client = await hass_ws_client(hass)
    created = await _call(client, 1, WS_TYPE_CREATE_CULTURE_MEDIUM, **A_MEDIUM)
    medium_id = created["result"]["medium"]["id"]
    await _call(
        client,
        2,
        WS_TYPE_UPDATE_CULTURE_MEDIUM,
        medium_id=medium_id,
        **{**A_MEDIUM, "agar_g_per_l": 8.0},
    )

    response = await _call(client, 3, WS_TYPE_LIST_CULTURE_MEDIA)

    assert response["success"]
    (medium,) = response["result"]["culture_media"]
    assert [version["agar_g_per_l"] for version in medium["versions"]] == [7.0, 8.0]


async def test_deleting_removes_the_medium(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Delete answers with the ID it removed, and the library is empty after."""
    client = await hass_ws_client(hass)
    created = await _call(client, 1, WS_TYPE_CREATE_CULTURE_MEDIUM, **A_MEDIUM)
    medium_id = created["result"]["medium"]["id"]

    response = await _call(
        client, 2, WS_TYPE_DELETE_CULTURE_MEDIUM, medium_id=medium_id
    )

    assert response["success"]
    assert response["result"] == {"medium_id": medium_id}
    assert (await _call(client, 3, WS_TYPE_LIST_CULTURE_MEDIA))["result"] == {
        "culture_media": []
    }


async def test_a_rejected_value_is_a_sentence_the_grower_can_act_on(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Value rules reach the card as `validation_failed`, not `invalid_format`."""
    client = await hass_ws_client(hass)

    response = await _call(
        client, 1, WS_TYPE_CREATE_CULTURE_MEDIUM, **{**A_MEDIUM, "ph_target": 58}
    )

    assert not response["success"]
    assert response["error"]["code"] == WS_ERR_VALIDATION_FAILED
    assert response["error"]["message"] == "pH target must be between 3 and 9."


async def test_a_wrong_type_is_the_card_s_bug(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Gross type errors stay voluptuous', where they belong."""
    client = await hass_ws_client(hass)

    response = await _call(
        client, 1, WS_TYPE_CREATE_CULTURE_MEDIUM, **{**A_MEDIUM, "name": 5}
    )

    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"


async def test_a_duplicate_name_is_a_conflict(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """A clashing name gets its own code, so the card can point at the field."""
    client = await hass_ws_client(hass)
    await _call(client, 1, WS_TYPE_CREATE_CULTURE_MEDIUM, **A_MEDIUM)

    response = await _call(client, 2, WS_TYPE_CREATE_CULTURE_MEDIUM, **A_MEDIUM)

    assert not response["success"]
    assert response["error"]["code"] == WS_ERR_CONFLICT


async def test_an_unknown_medium_is_not_found(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """A card holding a deleted medium is told so rather than obeyed."""
    client = await hass_ws_client(hass)

    response = await _call(
        client, 1, WS_TYPE_DELETE_CULTURE_MEDIUM, medium_id="does-not-exist"
    )

    assert not response["success"]
    assert response["error"]["code"] == WS_ERR_NOT_FOUND


async def test_an_unexpected_failure_is_reported_rather_than_swallowed(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A bug in a handler answers the connection instead of hanging it."""
    client = await hass_ws_client(hass)
    with patch.object(
        entry.runtime_data.repository,
        "culture_media",
        side_effect=RuntimeError("the disk fell off"),
    ):
        response = await _call(client, 1, WS_TYPE_LIST_CULTURE_MEDIA)

    assert not response["success"]
    assert response["error"]["code"] == "unknown_error"
    assert "the disk fell off" in response["error"]["message"]
    assert "Unhandled error" in caplog.text


async def test_the_commands_refuse_once_the_entry_is_unloaded(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Home Assistant cannot unregister a command, so each one refuses itself."""
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)

    response = await _call(client, 1, WS_TYPE_LIST_CULTURE_MEDIA)

    assert not response["success"]
    assert response["error"]["code"] == WS_ERR_NOT_LOADED
