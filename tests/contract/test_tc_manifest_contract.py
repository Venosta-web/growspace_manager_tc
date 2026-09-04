"""Golden contract fixture for the TC manifest payload.

The card validates its zod schema against this recorded file, fetched straight
from this repository — the backend side of the contract lands first, so the card
never has to invent a wire shape.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from custom_components.growspace_manager_tc.storage_manager import StorageManager
from custom_components.growspace_manager_tc.websocket import async_build_manifest
from homeassistant.core import HomeAssistant

FIXTURE_PATH = (
    Path(__file__).parents[1] / "fixtures" / "contract" / "tc_manifest_response.json"
)
REGENERATION_COMMAND = (
    "../../.venv/bin/pytest tests/contract/test_tc_manifest_contract.py "
    "--regenerate-contract-fixture"
)

# The release version is pinned for the recording, the way the Growspace Manager
# fixtures pin the clock: it is a real field the card reads, but letting a
# version bump rewrite the golden payload would turn every release into a
# contract diff. `tests/test_websocket.py` proves the live value flows through.
CONTRACT_INTEGRATION_VERSION = "0.1.0"


async def _build_contract_payload(hass: HomeAssistant) -> dict[str, object]:
    """Return the manifest payload for an installation with recorded content."""
    storage = StorageManager(hass)
    storage.repository.load(
        {
            "culture_lines": {"line-1": {}, "line-2": {}},
            "cultures": {"culture-1": {}},
        }
    )

    with patch(
        "custom_components.growspace_manager_tc.websocket.manifest.async_get_integration",
        return_value=SimpleNamespace(version=CONTRACT_INTEGRATION_VERSION),
    ):
        return await async_build_manifest(hass, storage)


@pytest.mark.asyncio
async def test_tc_manifest_contract(
    hass: HomeAssistant, pytestconfig: pytest.Config
) -> None:
    """Keep the real manifest payload in sync with the golden fixture."""
    payload = json.loads(json.dumps(await _build_contract_payload(hass)))

    if pytestconfig.getoption("regenerate_contract_fixture"):
        FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE_PATH.write_text(
            f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8"
        )

    assert FIXTURE_PATH.exists(), (
        "TC manifest contract fixture is missing. Regenerate it with: "
        f"{REGENERATION_COMMAND}"
    )
    assert payload == json.loads(FIXTURE_PATH.read_text(encoding="utf-8")), (
        "TC manifest payload changed. Review the contract diff, then regenerate "
        f"with: {REGENERATION_COMMAND}"
    )
