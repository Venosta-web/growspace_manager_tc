"""Golden pairing payload produced by the repository the WS list reads."""

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

FIXTURE = Path(__file__).parents[1] / "fixtures/contract/tc_pairings_response.json"


def test_pairings_contract(pytestconfig: pytest.Config) -> None:
    repository = CultureRepository()
    with patch(
        "custom_components.growspace_manager_tc.models.culture_medium.new_medium_id",
        return_value="medium-1",
    ):
        repository.create_culture_medium(
            "MS",
            MediumFormulation.from_payload(
                {
                    "base_salts": "MS",
                    "agar_g_per_l": 7,
                    "sugar_g_per_l": 30,
                    "ph_target": 5.8,
                }
            ),
        )
    with patch(
        "custom_components.growspace_manager_tc.data_access.culture_repository.new_id",
        side_effect=["pairing-1", "pairing-2"],
    ):
        for phenotype_id, name in [
            ("strain-a:keeper", "Keeper"),
            ("deleted-phenotype", "Preserved name"),
        ]:
            repository.save_pairing(
                {
                    "phenotype_id": phenotype_id,
                    "phenotype_name": name,
                    "medium_id": "medium-1",
                    "notes": "Grower endorsed.",
                },
                now="2026-09-05T09:00:00+00:00",
            )
    payload = {"pairings": [row.to_dict() for row in repository.pairings()]}
    if pytestconfig.getoption("regenerate_contract_fixture"):
        FIXTURE.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    assert payload == json.loads(FIXTURE.read_text())
