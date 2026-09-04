"""Golden contract fixture for the Maintenance Action history payload.

The card validates its zod schema against this recorded file, fetched straight
from this repository — the backend side of the contract lands first, so the card
never has to invent a wire shape.

The recording holds one of each of the five acts, because the payload is one
flat shape whose per-act fields are null or empty for the acts that do not use
them, and the only way to prove that is to record all five side by side.  The
Replate in it divides one Culture into two so the `vessels` list is exercised
with the shape a division actually produces: the replated Culture first, the new
one after it, each with the count and the shelf it went to.
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
from custom_components.growspace_manager_tc.models.culture_line import (
    PhenotypeReference,
    ReplateIntervals,
)
from custom_components.growspace_manager_tc.models.culture_medium import (
    MediumFormulation,
)

FIXTURE_PATH = (
    Path(__file__).parents[1] / "fixtures" / "contract" / "tc_maintenance_response.json"
)
REGENERATION_COMMAND = (
    "../../.venv/bin/pytest tests/contract/test_tc_maintenance_contract.py "
    "--regenerate-contract-fixture"
)

# IDs and timestamps are pinned for the recording, the way the other fixtures
# pin them: both are real fields the card reads, but letting a clock or a UUID
# rewrite the golden payload would turn every run into a contract diff.
RECORDED_TIMES = [
    "2026-01-04T09:12:00+00:00",
    "2026-02-03T09:20:00+00:00",
    "2026-02-24T11:00:00+00:00",
    "2026-03-17T14:35:00+00:00",
    "2026-03-30T08:05:00+00:00",
]
INTERVALS = {"multiplication": 30, "rooting": 21}
FORMULATION = {
    "base_salts": "MS full strength",
    "additives": [{"name": "Myo-inositol", "amount": 100.0, "unit": "mg/L"}],
    "hormones": [{"name": "BAP", "amount": 1.0, "unit": "mg/L"}],
    "agar_g_per_l": 7.0,
    "sugar_g_per_l": 30.0,
    "ph_target": 5.8,
    "notes": "",
}


def _build_contract_payload() -> dict[str, object]:
    """Return the `maintenance/history` payload for a recorded season's work."""
    ids = (f"record-{index}" for index in count(1))
    repository = CultureRepository()

    with (
        patch(
            "custom_components.growspace_manager_tc.models.culture_line.new_id",
            side_effect=lambda: next(ids),
        ),
        patch(
            "custom_components.growspace_manager_tc.models.culture_medium.new_id",
            side_effect=lambda: next(ids),
        ),
        patch(
            "custom_components.growspace_manager_tc.models.maintenance.new_id",
            side_effect=lambda: next(ids),
        ),
    ):
        medium = repository.create_culture_medium(
            "MS + BAP 1.0",
            MediumFormulation.from_payload(FORMULATION),
            now=RECORDED_TIMES[0],
        )
        line, culture = repository.introduce_culture_line(
            PhenotypeReference.taken(
                "Blue Dream|Pheno 2", "Blue Dream — Pheno 2", now=RECORDED_TIMES[0]
            ),
            ReplateIntervals.from_payload(INTERVALS),
            plantlet_count=6,
            location="Shelf A",
            now=RECORDED_TIMES[0],
        )

        # A division: the replated Culture, then the vessel it was split into.
        replate = repository.replate_culture(
            culture.id,
            medium.id,
            medium.current_version.version,
            [
                {"plantlet_count": 5, "location": "Shelf A"},
                {"plantlet_count": 4, "location": "Shelf B"},
            ],
            note="Divided the healthy half.",
            now=RECORDED_TIMES[1],
        )
        split_off = replate.vessels[1].culture_id

        repository.note_on_culture(
            culture.id, "Slight vitrification on two plantlets.", now=RECORDED_TIMES[2]
        )
        repository.move_culture_to_rooting(culture.id, now=RECORDED_TIMES[3])
        repository.graduate_culture(
            culture.id, note="Out to the humidity dome.", now=RECORDED_TIMES[4]
        )
        repository.discard_culture(
            split_off, "contamination", note="Bacterial haze.", now=RECORDED_TIMES[4]
        )

    assert line.id
    return {
        "actions": [action.to_dict() for action in repository.maintenance_actions()]
    }


def test_tc_maintenance_contract(pytestconfig: pytest.Config) -> None:
    """Keep the real history payload in sync with the golden fixture."""
    payload = json.loads(json.dumps(_build_contract_payload()))

    if pytestconfig.getoption("regenerate_contract_fixture"):
        FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE_PATH.write_text(
            f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8"
        )

    assert FIXTURE_PATH.exists(), (
        "TC maintenance contract fixture is missing. Regenerate it with: "
        f"{REGENERATION_COMMAND}"
    )
    assert payload == json.loads(FIXTURE_PATH.read_text(encoding="utf-8")), (
        "TC maintenance payload changed. Review the contract diff, then "
        f"regenerate with: {REGENERATION_COMMAND}"
    )
