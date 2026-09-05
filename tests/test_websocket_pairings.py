"""Pairing CRUD through the registered namespace and persistent store."""

from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.growspace_manager_tc.const import DOMAIN, STORAGE_KEY
from homeassistant.core import HomeAssistant


@pytest.fixture
async def entry(hass: HomeAssistant, growspace_manager_loaded: None) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_crud_and_failures(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    client = await hass_ws_client(hass)
    message_id = 0

    async def call(action: str, **payload: Any) -> dict[str, Any]:
        nonlocal message_id
        message_id += 1
        await client.send_json(
            {"id": message_id, "type": f"{DOMAIN}/{action}", **payload}
        )
        return await client.receive_json()

    assert (await call("pairings/list"))["result"] == {"pairings": []}
    medium = (
        await call(
            "culture_media/create",
            name="MS",
            base_salts="MS",
            agar_g_per_l=7,
            sugar_g_per_l=30,
            ph_target=5.8,
        )
    )["result"]["medium"]
    draft = {
        "phenotype_id": "opaque",
        "phenotype_name": "Keeper",
        "medium_id": medium["id"],
        "notes": "Roots well",
    }
    pairing = (await call("pairings/create", **draft))["result"]["pairing"]
    await hass.async_block_till_done()
    assert hass_storage[STORAGE_KEY]["data"]["pairings"][pairing["id"]] == pairing
    assert (await call("pairings/create", **draft))["error"]["code"] == "conflict"
    assert (await call("pairings/create", **{**draft, "phenotype_id": " "}))["error"][
        "code"
    ] == "validation_failed"
    assert (await call("pairings/create", **draft, medium_version=1))["error"][
        "code"
    ] == "invalid_format"
    assert (await call("pairings/update", pairing_id="missing", **draft))["error"][
        "code"
    ] == "entity_not_found"
    edited = (
        await call(
            "pairings/update", pairing_id=pairing["id"], **{**draft, "notes": "Updated"}
        )
    )["result"]["pairing"]
    assert (await call("pairings/list"))["result"] == {"pairings": [edited]}
    assert edited["notes"] == "Updated"
    assert (await call("pairings/delete", pairing_id=pairing["id"]))["result"] == {
        "pairing_id": pairing["id"]
    }
    assert (await call("pairings/list"))["result"] == {"pairings": []}
    assert hass_storage[STORAGE_KEY]["data"]["pairings"] == {}
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert (await call("pairings/list"))["error"]["code"] == "not_loaded"
