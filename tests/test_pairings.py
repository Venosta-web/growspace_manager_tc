"""Pairing identity, repair, persistence and medium-version independence."""

import pytest

from custom_components.growspace_manager_tc.data_access.culture_repository import (
    CultureRepository,
)
from custom_components.growspace_manager_tc.models.common import (
    TcConflictError,
    TcNotFoundError,
    TcValidationError,
)
from custom_components.growspace_manager_tc.models.culture_medium import (
    MediumFormulation,
)

FORMULATION = {
    "base_salts": "MS",
    "agar_g_per_l": 7,
    "sugar_g_per_l": 30,
    "ph_target": 5.8,
}


@pytest.fixture
def repository() -> CultureRepository:
    repo = CultureRepository()
    repo.create_culture_medium("MS", MediumFormulation.from_payload(FORMULATION))
    return repo


def draft(repository: CultureRepository, **changes: object) -> dict:
    return {
        "phenotype_id": "opaque:1",
        "phenotype_name": "Keeper",
        "medium_id": repository.culture_media()[0].id,
        "notes": " Good roots. ",
        **changes,
    }


def test_unique_pair_on_create_and_update(repository: CultureRepository) -> None:
    first = repository.save_pairing(draft(repository))
    with pytest.raises(TcConflictError):
        repository.save_pairing(draft(repository, phenotype_name="Renamed"))
    second = repository.save_pairing(draft(repository, phenotype_id="opaque:2"))
    before = repository.as_dict()
    with pytest.raises(TcConflictError):
        repository.save_pairing(draft(repository), pairing_id=second.id)
    assert repository.as_dict() == before
    assert repository.pairing(first.id).notes == "Good roots."


def test_repair_and_reload_preserve_identity(repository: CultureRepository) -> None:
    first = repository.save_pairing(draft(repository), now="2026-01-01")
    edited = repository.save_pairing(
        draft(repository, phenotype_id="new", phenotype_name="New keeper", notes=""),
        pairing_id=first.id,
        now="2026-02-01",
    )
    assert edited.id == first.id
    assert edited.created_at == first.created_at
    assert edited.phenotype.id == "new"
    restored = CultureRepository()
    restored.load(repository.as_dict())
    assert restored.pairings() == [edited]
    assert restored.delete_pairing(edited.id) == edited
    assert restored.pairings() == []


def test_endorses_medium_across_versions_and_guards_deletion(
    repository: CultureRepository,
) -> None:
    pairing = repository.save_pairing(draft(repository))
    repository.update_culture_medium(
        pairing.medium_id,
        "Renamed",
        MediumFormulation.from_payload({**FORMULATION, "ph_target": 5.6}),
    )
    assert repository.pairing(pairing.id) == pairing
    assert "medium_version" not in pairing.to_dict()
    with pytest.raises(TcConflictError):
        repository.delete_culture_medium(pairing.medium_id)
    repository.delete_pairing(pairing.id)
    repository.delete_culture_medium(pairing.medium_id)


@pytest.mark.parametrize(
    "changes",
    [
        {"phenotype_id": " "},
        {"phenotype_name": ""},
        {"notes": "x" * 4001},
        {"medium_id": ""},
    ],
)
def test_invalid_inputs_do_not_mutate(
    repository: CultureRepository, changes: dict
) -> None:
    before = repository.as_dict()
    with pytest.raises(TcValidationError):
        repository.save_pairing(draft(repository, **changes))
    assert repository.as_dict() == before


def test_missing_references_and_records(repository: CultureRepository) -> None:
    with pytest.raises(TcNotFoundError):
        repository.save_pairing(draft(repository, medium_id="missing"))
    with pytest.raises(TcNotFoundError):
        repository.save_pairing(draft(repository), pairing_id="missing")
    with pytest.raises(TcNotFoundError):
        repository.delete_pairing("missing")


def test_unreadable_pairings_survive_save() -> None:
    repo = CultureRepository()
    repo.load({"pairings": {"future": {"unknown": True}}})
    assert repo.pairings() == []
    assert repo.as_dict()["pairings"] == {"future": {"unknown": True}}
