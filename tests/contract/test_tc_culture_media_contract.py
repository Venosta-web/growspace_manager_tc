"""Golden contract fixture for the Culture Medium library payload.

The card validates its zod schema against this recorded file, fetched straight
from this repository — the backend side of the contract lands first, so the card
never has to invent a wire shape.

The recording is deliberately not a fresh library: one medium still at version 1
and one edited twice, so the fixture carries the thing the contract is actually
about (ADR-0004) rather than only the empty case.
"""

from __future__ import annotations

from itertools import count
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from custom_components.growspace_manager_tc.data_access.culture_repository import (
    CultureRepository,
)
from custom_components.growspace_manager_tc.models.culture_medium import (
    MediumFormulation,
)

FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "fixtures"
    / "contract"
    / "tc_culture_media_response.json"
)
REGENERATION_COMMAND = (
    "../../.venv/bin/pytest tests/contract/test_tc_culture_media_contract.py "
    "--regenerate-contract-fixture"
)

# IDs and timestamps are pinned for the recording, the way the manifest fixture
# pins the release version: both are real fields the card reads, but letting a
# clock or a UUID rewrite the golden payload would turn every run into a
# contract diff.
RECORDED_TIMES = [
    "2026-01-04T09:12:00+00:00",
    "2026-02-18T16:40:00+00:00",
    "2026-03-30T08:05:00+00:00",
]


def _multiplication_medium(version: int) -> MediumFormulation:
    """Return the multiplication formulation as it stood at `version`."""
    return MediumFormulation.from_payload(
        {
            "base_salts": "MS",
            "additives": [
                {"name": "myo-inositol", "amount": 100.0, "unit": "mg/L"},
                {"name": "thiamine HCl", "amount": 0.4, "unit": "mg/L"},
            ],
            "hormones": [{"name": "BAP", "amount": 0.5 * version, "unit": "mg/L"}],
            "agar_g_per_l": 7.0,
            "sugar_g_per_l": 30.0,
            "ph_target": 5.8,
            "notes": "Autoclave 15 min at 121 °C.",
        }
    )


def _build_contract_payload() -> dict[str, object]:
    """Return the `culture_media/list` payload for a recorded library."""
    ids = (f"medium-{index}" for index in count(1))
    repository = CultureRepository()

    with patch(
        "custom_components.growspace_manager_tc.models.culture_medium.new_medium_id",
        side_effect=lambda: next(ids),
    ):
        multiplication = repository.create_culture_medium(
            "MS multiplication", _multiplication_medium(1), now=RECORDED_TIMES[0]
        )
        repository.create_culture_medium(
            "Half MS rooting",
            MediumFormulation.from_payload(
                {
                    "base_salts": "½ MS",
                    "hormones": [{"name": "IBA", "amount": 0.25, "unit": "mg/L"}],
                    "agar_g_per_l": 6.0,
                    "sugar_g_per_l": 20.0,
                    "ph_target": 5.6,
                }
            ),
            now=RECORDED_TIMES[0],
        )

    # Two edits of the same medium, so the fixture carries a version history a
    # card can render rather than a single snapshot it could mistake for the
    # whole shape.
    for index, version in ((1, 2), (2, 3)):
        repository.update_culture_medium(
            multiplication.id,
            "MS multiplication",
            _multiplication_medium(version),
            now=RECORDED_TIMES[index],
        )

    return {
        "culture_media": [medium.to_dict() for medium in repository.culture_media()]
    }


def test_tc_culture_media_contract(pytestconfig: pytest.Config) -> None:
    """Keep the real library payload in sync with the golden fixture."""
    payload = json.loads(json.dumps(_build_contract_payload()))

    if pytestconfig.getoption("regenerate_contract_fixture"):
        FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE_PATH.write_text(
            f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8"
        )

    assert FIXTURE_PATH.exists(), (
        "TC culture media contract fixture is missing. Regenerate it with: "
        f"{REGENERATION_COMMAND}"
    )
    assert payload == json.loads(FIXTURE_PATH.read_text(encoding="utf-8")), (
        "TC culture media payload changed. Review the contract diff, then "
        f"regenerate with: {REGENERATION_COMMAND}"
    )
