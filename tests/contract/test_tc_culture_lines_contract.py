"""Golden contract fixture for the culture board payload.

The card validates its zod schema against this recorded file, fetched straight
from this repository — the backend side of the contract lands first, so the card
never has to invent a wire shape.

The recording is deliberately not a fresh board.  It holds a live line, a line
whose phenotype was later re-linked, and an archived one, because the shapes the
card has to get right are exactly those: a Phenotype Reference with its name
snapshot, the per-stage intervals, and an `archived_at` that is a stamp rather
than a flag.  What it cannot hold is a Missing Phenotype — that state is the
card's verdict after a client-side join against Growspace Manager's strain
library (ADR-0002), and this repository has no way to produce or record it.
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

FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "fixtures"
    / "contract"
    / "tc_culture_lines_response.json"
)
REGENERATION_COMMAND = (
    "../../.venv/bin/pytest tests/contract/test_tc_culture_lines_contract.py "
    "--regenerate-contract-fixture"
)

# IDs and timestamps are pinned for the recording, the way the media fixture
# pins them: both are real fields the card reads, but letting a clock or a UUID
# rewrite the golden payload would turn every run into a contract diff.
RECORDED_TIMES = [
    "2026-01-04T09:12:00+00:00",
    "2026-02-18T16:40:00+00:00",
    "2026-03-30T08:05:00+00:00",
]
INTERVALS = {"multiplication": 30, "rooting": 21}


def _build_contract_payload() -> dict[str, object]:
    """Return the `culture_lines/list` payload for a recorded board."""
    ids = (f"record-{index}" for index in count(1))
    repository = CultureRepository()

    with patch(
        "custom_components.growspace_manager_tc.models.culture_line.new_id",
        side_effect=lambda: next(ids),
    ):
        repository.introduce_culture_line(
            PhenotypeReference.taken(
                "Blue Dream|Pheno 2", "Blue Dream — Pheno 2", now=RECORDED_TIMES[0]
            ),
            ReplateIntervals.from_payload(INTERVALS),
            plantlet_count=6,
            location="Shelf A",
            now=RECORDED_TIMES[0],
        )
        relinked, _ = repository.introduce_culture_line(
            PhenotypeReference.taken(
                "Gelato 33|Cut A", "Gelato 33 — Cut A", now=RECORDED_TIMES[0]
            ),
            ReplateIntervals.from_payload(INTERVALS),
            stage="rooting",
            now=RECORDED_TIMES[1],
        )
        archived, _ = repository.introduce_culture_line(
            PhenotypeReference.taken(
                "Zkittlez|Cut 4", "Zkittlez — Cut 4", now=RECORDED_TIMES[0]
            ),
            ReplateIntervals.from_payload(INTERVALS),
            now=RECORDED_TIMES[1],
        )

    # A re-link and an archive, so the fixture carries the two ways out of a
    # Missing Phenotype rather than only the state that never went wrong.
    with patch(
        "custom_components.growspace_manager_tc.models.culture_line.utc_now_iso",
        return_value=RECORDED_TIMES[2],
    ):
        repository.relink_phenotype(
            relinked.id,
            PhenotypeReference.taken(
                "Gelato 33|Cut B", "Gelato 33 — Cut B", now=RECORDED_TIMES[2]
            ),
        )
        repository.set_culture_line_archived(archived.id, True)

    return {
        "culture_lines": [
            line.to_payload(repository.cultures_of(line.id))
            for line in repository.culture_lines()
        ]
    }


def test_tc_culture_lines_contract(pytestconfig: pytest.Config) -> None:
    """Keep the real board payload in sync with the golden fixture."""
    payload = json.loads(json.dumps(_build_contract_payload()))

    if pytestconfig.getoption("regenerate_contract_fixture"):
        FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE_PATH.write_text(
            f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8"
        )

    assert FIXTURE_PATH.exists(), (
        "TC culture lines contract fixture is missing. Regenerate it with: "
        f"{REGENERATION_COMMAND}"
    )
    assert payload == json.loads(FIXTURE_PATH.read_text(encoding="utf-8")), (
        "TC culture lines payload changed. Review the contract diff, then "
        f"regenerate with: {REGENERATION_COMMAND}"
    )
