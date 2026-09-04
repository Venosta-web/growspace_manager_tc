"""Tests for the TC WebSocket namespace and its presence contract."""

import json
from pathlib import Path
from typing import Any

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.growspace_manager_tc.const import (
    DOMAIN,
    FEATURE_CULTURE_LINES,
    FEATURE_CULTURE_MEDIA,
    FEATURE_MAINTENANCE,
    STORAGE_KEY,
    STORAGE_VERSION,
    TC_CONTRACT_VERSION,
    WS_ERR_NOT_LOADED,
)
from custom_components.growspace_manager_tc.websocket import WS_TYPE_GET_MANIFEST
from homeassistant.core import HomeAssistant

MANIFEST_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "growspace_manager_tc"
    / "manifest.json"
)


async def _setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_namespace_is_absent_without_the_integration(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Nothing registers the namespace until an entry loads.

    This is the whole presence signal: a card asking a Home Assistant without
    Growspace Manager TC gets `unknown_command` back, not an empty answer.
    """
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": WS_TYPE_GET_MANIFEST})
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unknown_command"


async def test_manifest_reports_the_contract(
    hass: HomeAssistant,
    growspace_manager_loaded: None,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """A loaded entry answers with the contract it speaks and what it holds."""
    await _setup_entry(hass)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": WS_TYPE_GET_MANIFEST})
    response = await client.receive_json()

    assert response["success"]
    installed_version = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["version"]
    assert response["result"] == {
        "contract_version": TC_CONTRACT_VERSION,
        "integration_version": installed_version,
        "features": [FEATURE_CULTURE_MEDIA, FEATURE_CULTURE_LINES, FEATURE_MAINTENANCE],
        "collections": {
            "culture_media": 0,
            "culture_lines": 0,
            "cultures": 0,
            "maintenance_actions": 0,
        },
    }


async def test_manifest_counts_persisted_collections(
    hass: HomeAssistant,
    growspace_manager_loaded: None,
    hass_storage: dict[str, Any],
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Collections are counted, and non-collection payload entries are not."""
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "data": {
            "culture_lines": {"line-1": {}, "line-2": {}},
            "cultures": [],
            "schema_marker": "written-by-a-newer-version",
        },
    }
    await _setup_entry(hass)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": WS_TYPE_GET_MANIFEST})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["collections"] == {
        "culture_lines": 2,
        "cultures": 0,
        "culture_media": 0,
        "maintenance_actions": 0,
    }


async def test_manifest_refuses_once_the_entry_is_unloaded(
    hass: HomeAssistant,
    growspace_manager_loaded: None,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """The command outlives the entry, so it has to refuse for itself.

    Home Assistant cannot unregister a WebSocket command; without this the
    namespace would keep claiming an integration that is no longer running.
    """
    entry = await _setup_entry(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": WS_TYPE_GET_MANIFEST})
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == WS_ERR_NOT_LOADED


async def test_reloading_re_registers_the_namespace(
    hass: HomeAssistant,
    growspace_manager_loaded: None,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Registration is idempotent: a reload does not break the namespace."""
    entry = await _setup_entry(hass)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": WS_TYPE_GET_MANIFEST})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["contract_version"] == TC_CONTRACT_VERSION
