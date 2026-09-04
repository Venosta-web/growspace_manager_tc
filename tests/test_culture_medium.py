"""Tests for Culture Media, their versions, and the library that holds them."""

from typing import Any

import pytest

from custom_components.growspace_manager_tc.data_access.culture_repository import (
    CultureRepository,
)
from custom_components.growspace_manager_tc.models.culture_medium import (
    CultureMedium,
    MediumFormulation,
    MediumNameConflictError,
    MediumNotFoundError,
    MediumValidationError,
)

A_FORMULATION: dict[str, Any] = {
    "base_salts": "MS",
    "additives": [{"name": "myo-inositol", "amount": 100, "unit": "mg/L"}],
    "hormones": [{"name": "BAP", "amount": 1.0, "unit": "mg/L"}],
    "agar_g_per_l": 7.0,
    "sugar_g_per_l": 30.0,
    "ph_target": 5.8,
    "notes": "Autoclave 15 min.",
}


def a_formulation(**overrides: Any) -> MediumFormulation:
    """Return the reference formulation with fields replaced."""
    return MediumFormulation.from_payload({**A_FORMULATION, **overrides})


# -- validation -----------------------------------------------------------


def test_formulation_trims_and_defaults() -> None:
    """Text is stored trimmed, and the optional parts have empty defaults."""
    formulation = MediumFormulation.from_payload(
        {
            "base_salts": "  MS  ",
            "agar_g_per_l": 7,
            "sugar_g_per_l": 30,
            "ph_target": 5.8,
        }
    )

    assert formulation.base_salts == "MS"
    assert formulation.additives == ()
    assert formulation.hormones == ()
    assert formulation.notes == ""


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"base_salts": "   "}, "Base salts is required."),
        ({"base_salts": 5}, "Base salts must be text."),
        ({"agar_g_per_l": "7"}, "Agar must be a number."),
        ({"agar_g_per_l": True}, "Agar must be a number."),
        ({"agar_g_per_l": -1}, "Agar must be between 0 and 30."),
        ({"sugar_g_per_l": 500}, "Sugar must be between 0 and 100."),
        ({"ph_target": 58}, "pH target must be between 3 and 9."),
        ({"hormones": {"name": "BAP"}}, "Hormone must be a list."),
        ({"hormones": ["BAP"]}, "Each Hormone entry must be an object."),
        (
            {"additives": [{"name": "", "amount": 1, "unit": "mg/L"}]},
            "Additive name is required.",
        ),
        (
            {"additives": [{"name": "agar", "amount": -1, "unit": "g/L"}]},
            "Additive amount must be between 0 and 100000.",
        ),
        (
            {"additives": [{"name": "agar", "amount": 1, "unit": " "}]},
            "Additive unit is required.",
        ),
    ],
)
def test_formulation_rejects(overrides: dict[str, Any], message: str) -> None:
    """Every rejection names the field and says what is wrong with it."""
    with pytest.raises(MediumValidationError, match=message.replace(".", r"\.")):
        a_formulation(**overrides)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"base_salts": "M" * 121}, "Base salts must be at most 120 characters."),
        ({"notes": "n" * 2001}, "Notes must be at most 2000 characters."),
        ({"notes": 5}, "Notes must be text."),
        (
            {
                "additives": [
                    {"name": f"additive {index}", "amount": 1, "unit": "mg/L"}
                    for index in range(41)
                ]
            },
            "Additive may hold at most 40 entries.",
        ),
    ],
)
def test_formulation_has_limits(overrides: dict[str, Any], message: str) -> None:
    """Limits exist to catch a paste, not to have an opinion about recipes."""
    with pytest.raises(MediumValidationError, match=message.replace(".", r"\.")):
        a_formulation(**overrides)


def test_a_component_cannot_be_listed_twice() -> None:
    """Two rows for one hormone are a typo, not two doses."""
    with pytest.raises(MediumValidationError, match="twice"):
        a_formulation(
            hormones=[
                {"name": "BAP", "amount": 1.0, "unit": "mg/L"},
                {"name": "bap", "amount": 0.5, "unit": "mg/L"},
            ]
        )


def test_pi_is_not_a_ph() -> None:
    """A number that is not finite is not a measurement."""
    with pytest.raises(MediumValidationError, match="pH target must be a number"):
        a_formulation(ph_target=float("nan"))


# -- versions -------------------------------------------------------------


def test_a_new_medium_starts_at_version_one() -> None:
    """Creating a medium records its first snapshot."""
    medium = CultureMedium.create(
        "MS", a_formulation(), now="2026-01-01T00:00:00+00:00"
    )

    assert medium.current_version.version == 1
    assert len(medium.versions) == 1


def test_editing_the_formulation_forks_a_version() -> None:
    """The prior version stays readable and unchanged (ADR-0004)."""
    medium = CultureMedium.create(
        "MS", a_formulation(), now="2026-01-01T00:00:00+00:00"
    )
    original = medium.current_version

    edited = medium.edited(
        "MS", a_formulation(ph_target=5.6), now="2026-02-01T00:00:00+00:00"
    )

    assert [version.version for version in edited.versions] == [1, 2]
    assert edited.versions[0] == original
    assert edited.versions[0].formulation.ph_target == 5.8
    assert edited.current_version.formulation.ph_target == 5.6
    assert edited.current_version.created_at == "2026-02-01T00:00:00+00:00"


def test_saving_an_unchanged_formulation_forks_nothing() -> None:
    """A version is minted by a change, not by pressing save."""
    medium = CultureMedium.create(
        "MS", a_formulation(), now="2026-01-01T00:00:00+00:00"
    )

    assert (
        medium.edited("MS", a_formulation(), now="2026-02-01T00:00:00+00:00") is medium
    )


def test_renaming_forks_nothing() -> None:
    """The name labels the lineage; a Plating pins the formulation, not it."""
    medium = CultureMedium.create(
        "MS", a_formulation(), now="2026-01-01T00:00:00+00:00"
    )

    renamed = medium.edited(
        "MS multiplication", a_formulation(), now="2026-02-01T00:00:00+00:00"
    )

    assert renamed.name == "MS multiplication"
    assert renamed.versions == medium.versions
    assert renamed.updated_at == "2026-02-01T00:00:00+00:00"


def test_a_medium_round_trips_through_the_store() -> None:
    """What was persisted decodes back to the same medium."""
    medium = CultureMedium.create(
        "MS", a_formulation(), now="2026-01-01T00:00:00+00:00"
    )
    edited = medium.edited(
        "MS", a_formulation(agar_g_per_l=8), now="2026-02-01T00:00:00+00:00"
    )

    assert CultureMedium.from_dict(edited.id, edited.to_dict()) == edited


@pytest.mark.parametrize("version", [0, -1, "2", True, None])
def test_a_version_number_must_be_a_positive_integer(version: Any) -> None:
    """Versions are counted, and the count is what a Plating pins."""
    with pytest.raises(MediumValidationError, match="positive integer"):
        CultureMedium.from_dict(
            "medium-1",
            {
                "name": "MS",
                "created_at": "2026-01-01T00:00:00+00:00",
                "versions": [
                    {
                        "version": version,
                        "created_at": "2026-01-01T00:00:00+00:00",
                        **A_FORMULATION,
                    }
                ],
            },
        )


def test_a_medium_needs_at_least_one_version() -> None:
    """A formulation-less medium is not a medium."""
    with pytest.raises(MediumValidationError, match="at least one version"):
        CultureMedium.from_dict(
            "medium-1",
            {"name": "MS", "created_at": "2026-01-01T00:00:00+00:00", "versions": []},
        )


# -- the library ----------------------------------------------------------


def test_the_library_is_ordered_by_name() -> None:
    """Media come back in the order they are shown, case regardless."""
    repository = CultureRepository()
    for name in ("rooting", "MS", "b5"):
        repository.create_culture_medium(name, a_formulation(base_salts=name))

    assert [medium.name for medium in repository.culture_media()] == [
        "b5",
        "MS",
        "rooting",
    ]


def test_a_name_cannot_be_claimed_twice() -> None:
    """Two rows nobody can tell apart would make a Pairing unreadable."""
    repository = CultureRepository()
    repository.create_culture_medium("MS multiplication", a_formulation())

    with pytest.raises(MediumNameConflictError, match="already exists"):
        repository.create_culture_medium("ms MULTIPLICATION", a_formulation())


def test_a_medium_may_keep_its_own_name_while_being_edited() -> None:
    """The uniqueness check does not count the medium against itself."""
    repository = CultureRepository()
    medium = repository.create_culture_medium("MS", a_formulation())

    updated = repository.update_culture_medium(
        medium.id, "MS", a_formulation(ph_target=5.6)
    )

    assert updated.current_version.version == 2


def test_updating_an_unknown_medium_is_not_found() -> None:
    """A stale card must not be able to resurrect a deleted medium."""
    with pytest.raises(MediumNotFoundError):
        CultureRepository().update_culture_medium("nope", "MS", a_formulation())


def test_deleting_removes_the_medium_and_its_history() -> None:
    """Nothing pins a version yet, so the whole lineage goes."""
    repository = CultureRepository()
    medium = repository.create_culture_medium("MS", a_formulation())

    repository.delete_culture_medium(medium.id)

    assert repository.culture_media() == []
    with pytest.raises(MediumNotFoundError):
        repository.delete_culture_medium(medium.id)


def test_media_survive_a_load_save_cycle() -> None:
    """A library written to the store comes back as it went in."""
    repository = CultureRepository()
    repository.create_culture_medium("MS", a_formulation())
    persisted = repository.as_dict()

    reloaded = CultureRepository()
    reloaded.load(persisted)

    assert reloaded.as_dict() == persisted
    assert reloaded.culture_media() == repository.culture_media()


def test_an_unreadable_medium_is_kept_rather_than_dropped() -> None:
    """A record this version cannot decode still survives the cycle."""
    repository = CultureRepository()
    repository.load(
        {
            "culture_media": {
                "future-1": {"name": "MS", "written_by": "a newer version"},
            }
        }
    )

    assert repository.culture_media() == []
    assert repository.as_dict()["culture_media"] == {
        "future-1": {"name": "MS", "written_by": "a newer version"}
    }
    assert repository.collection_sizes()["culture_media"] == 1


def test_an_unreadable_collection_is_kept_whole() -> None:
    """A `culture_media` that is not a collection is left exactly as found."""
    repository = CultureRepository()
    repository.load({"culture_media": ["written", "by", "something", "else"]})

    assert repository.culture_media() == []
    assert repository.as_dict() == {
        "culture_media": ["written", "by", "something", "else"]
    }
