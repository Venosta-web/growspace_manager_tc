"""Tests for Culture Lines, their Cultures, and the Phenotype Reference."""

from typing import Any

import pytest

from custom_components.growspace_manager_tc.data_access.culture_repository import (
    CultureRepository,
)
from custom_components.growspace_manager_tc.models.common import (
    TcNotFoundError,
    TcValidationError,
)
from custom_components.growspace_manager_tc.models.culture_line import (
    Culture,
    CultureLine,
    CultureStage,
    CultureStatus,
    PhenotypeReference,
    ReplateIntervals,
)

INTERVALS: dict[str, Any] = {"multiplication": 30, "rooting": 21}
A_TIME = "2026-01-04T09:12:00+00:00"
LATER = "2026-02-18T16:40:00+00:00"


def _reference(
    phenotype_id: str = "Blue Dream|Pheno 2", name: str = "Blue Dream — Pheno 2"
) -> PhenotypeReference:
    return PhenotypeReference.taken(phenotype_id, name, now=A_TIME)


def _introduce(
    repository: CultureRepository, **kwargs: Any
) -> tuple[CultureLine, Culture]:
    return repository.introduce_culture_line(
        kwargs.pop("phenotype", None) or _reference(),
        ReplateIntervals.from_payload(kwargs.pop("intervals", None) or INTERVALS),
        **kwargs,
    )


# -- the phenotype reference ------------------------------------------------


def test_a_reference_keeps_the_id_opaque() -> None:
    """Nothing here parses the ID: it is Growspace Manager's to shape."""
    reference = PhenotypeReference.taken("anything at all", "A name", now=A_TIME)

    assert reference.id == "anything at all"
    assert reference.to_dict() == {
        "id": "anything at all",
        "name_snapshot": "A name",
        "snapshot_at": A_TIME,
    }


def test_a_reference_needs_both_the_id_and_the_name() -> None:
    """A snapshot with no name is a Missing Phenotype nobody could label."""
    with pytest.raises(TcValidationError, match="Phenotype name is required"):
        PhenotypeReference.taken("Blue Dream|Pheno 2", "   ")

    with pytest.raises(TcValidationError, match="Phenotype is required"):
        PhenotypeReference.taken("", "Blue Dream")


def test_a_persisted_line_without_a_reference_is_unreadable() -> None:
    """A line is a reference plus intervals; without one it is not a line."""
    with pytest.raises(TcValidationError, match="phenotype reference"):
        PhenotypeReference.from_dict(None)


def test_a_reference_round_trips_through_storage() -> None:
    """What was persisted decodes back to the same reference."""
    reference = _reference()

    assert PhenotypeReference.from_dict(reference.to_dict()) == reference


# -- intervals --------------------------------------------------------------


def test_intervals_are_required_for_every_stage() -> None:
    """A missing interval would produce an invented Replate Due Date."""
    with pytest.raises(TcValidationError, match="Rooting interval"):
        ReplateIntervals.from_payload({"multiplication": 30})


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (0, "between 1 and 365"),
        (400, "between 1 and 365"),
        (30.5, "whole number"),
        (True, "whole number"),
        ("30", "whole number"),
    ],
)
def test_intervals_reject_values_the_grower_has_to_fix(
    value: Any, message: str
) -> None:
    """Each rejection names the field and says what is wrong with it."""
    with pytest.raises(TcValidationError, match=message):
        ReplateIntervals.from_payload({"multiplication": value, "rooting": 21})


def test_intervals_that_are_not_a_mapping_are_refused() -> None:
    """A scalar where the per-stage object belongs names the whole field."""
    with pytest.raises(TcValidationError, match="every culture stage"):
        ReplateIntervals.from_payload(30)


def test_an_interval_is_selected_by_the_stage() -> None:
    """The stage is what picks which of the line's intervals applies."""
    intervals = ReplateIntervals.from_payload(INTERVALS)

    assert intervals.for_stage(CultureStage.MULTIPLICATION) == 30
    assert intervals.for_stage(CultureStage.ROOTING) == 21


# -- the introduction -------------------------------------------------------


def test_an_introduction_creates_a_line_and_its_first_culture() -> None:
    """One Introduction, one line, one first vessel — written together."""
    repository = CultureRepository()

    line, culture = _introduce(repository, now=A_TIME)

    assert repository.culture_lines() == [line]
    assert repository.cultures_of(line.id) == (culture,)
    assert culture.line_id == line.id
    assert culture.status is CultureStatus.ACTIVE
    assert culture.stage is CultureStage.MULTIPLICATION


def test_an_introduction_anchors_the_replate_interval() -> None:
    """Placing the explant is a plating, so the culture starts with an anchor."""
    repository = CultureRepository()

    _line, culture = _introduce(repository, now=A_TIME)

    assert culture.started_at == A_TIME
    assert culture.last_replated_at == A_TIME


def test_an_introduction_may_start_in_rooting() -> None:
    """The stage is the grower's to choose; multiplication is only the default."""
    repository = CultureRepository()

    _line, culture = _introduce(repository, stage="rooting")

    assert culture.stage is CultureStage.ROOTING


def test_an_introduction_refuses_a_stage_nobody_defined_an_interval_for() -> None:
    """A third stage would select an interval the line does not carry."""
    repository = CultureRepository()

    with pytest.raises(TcValidationError, match="multiplication, rooting"):
        _introduce(repository, stage="callus")


def test_an_uncounted_culture_is_not_counted_as_zero() -> None:
    """ "Nobody counted" and "the vessel is empty" are different facts."""
    repository = CultureRepository()

    _line, uncounted = _introduce(repository)
    _line, empty = _introduce(repository, plantlet_count=0)

    assert uncounted.plantlet_count is None
    assert empty.plantlet_count == 0


def test_the_line_carries_the_snapshot_and_the_intervals() -> None:
    """The two things the Introduction exists to record are on the line."""
    repository = CultureRepository()

    line, _culture = _introduce(repository, now=A_TIME)

    assert line.phenotype.name_snapshot == "Blue Dream — Pheno 2"
    assert line.replate_interval_days.to_dict() == INTERVALS


# -- the two ways out of a missing phenotype --------------------------------


def test_relinking_replaces_the_whole_reference() -> None:
    """A line must never render under a name it no longer refers to."""
    repository = CultureRepository()
    line, _culture = _introduce(repository, now=A_TIME)

    relinked = repository.relink_phenotype(
        line.id, PhenotypeReference.taken("Gelato 33|Cut B", "Gelato 33 — Cut B")
    )

    assert relinked.phenotype.id == "Gelato 33|Cut B"
    assert relinked.phenotype.name_snapshot == "Gelato 33 — Cut B"
    assert repository.culture_lines() == [relinked]


def test_relinking_keeps_the_cultures() -> None:
    """The lineage in the vessels is the same lineage; only the label moved."""
    repository = CultureRepository()
    line, culture = _introduce(repository)

    repository.relink_phenotype(
        line.id, PhenotypeReference.taken("Gelato 33|Cut B", "Gelato 33 — Cut B")
    )

    assert repository.cultures_of(line.id) == (culture,)


def test_archiving_stamps_and_is_reversible() -> None:
    """Archiving is the honest move when a reference goes missing, so it is not
    a one-way door."""
    repository = CultureRepository()
    line, _culture = _introduce(repository)

    archived = repository.set_culture_line_archived(line.id, True)
    assert archived.archived_at is not None
    assert archived.archived

    restored = repository.set_culture_line_archived(line.id, False)
    assert restored.archived_at is None
    assert not restored.archived


def test_archiving_an_archived_line_keeps_the_original_stamp() -> None:
    """The interesting date is when it was put away, not the last button press."""
    repository = CultureRepository()
    line, _culture = _introduce(repository)
    archived = repository.set_culture_line_archived(line.id, True)

    again = repository.set_culture_line_archived(line.id, True)

    assert again.archived_at == archived.archived_at


def test_archiving_never_deletes_the_line_or_its_cultures() -> None:
    """A removed line would be indistinguishable from data loss."""
    repository = CultureRepository()
    line, culture = _introduce(repository)

    repository.set_culture_line_archived(line.id, True)

    assert repository.culture_line(line.id).archived
    assert repository.cultures_of(line.id) == (culture,)


@pytest.mark.parametrize(
    "act",
    [
        lambda repository: repository.relink_phenotype("nope", _reference()),
        lambda repository: repository.set_culture_line_archived("nope", True),
    ],
    ids=["relink", "archive"],
)
def test_acting_on_an_unknown_line_is_not_found(act: Any) -> None:
    """The card is told `entity_not_found`, not a broken backend."""
    repository = CultureRepository()

    with pytest.raises(TcNotFoundError):
        act(repository)


# -- ordering and persistence -----------------------------------------------


def test_the_board_lists_live_lines_before_archived_ones() -> None:
    """The board's order is the backend's, so two clients cannot disagree."""
    repository = CultureRepository()
    first, _ = _introduce(repository, phenotype=_reference("a|1", "Aaa"), now=A_TIME)
    second, _ = _introduce(repository, phenotype=_reference("z|1", "Zzz"), now=A_TIME)
    repository.set_culture_line_archived(first.id, True)

    assert [line.id for line in repository.culture_lines()] == [second.id, first.id]


def test_lines_and_cultures_round_trip_through_storage() -> None:
    """What was saved decodes back to the same board."""
    repository = CultureRepository()
    line, culture = _introduce(repository, plantlet_count=6, location="Shelf A")
    payload = repository.as_dict()

    reloaded = CultureRepository()
    reloaded.load(payload)

    assert reloaded.culture_line(line.id) == line
    assert reloaded.cultures_of(line.id) == (culture,)


def test_cultures_are_stored_beside_their_line_not_inside_it() -> None:
    """A Maintenance Action writes one vessel without rewriting its lineage."""
    repository = CultureRepository()
    line, culture = _introduce(repository)

    payload = repository.as_dict()

    assert "cultures" not in payload["culture_lines"][line.id]
    assert payload["cultures"][culture.id]["line_id"] == line.id


def test_a_line_this_version_cannot_read_is_kept_and_counted() -> None:
    """A store written by a newer version survives a load/save cycle."""
    repository = CultureRepository()
    repository.load({"culture_lines": {"future-1": {"written_by": "a newer version"}}})

    assert repository.culture_lines() == []
    assert repository.as_dict()["culture_lines"] == {
        "future-1": {"written_by": "a newer version"}
    }
    assert repository.collection_sizes()["culture_lines"] == 1


def test_the_wire_payload_carries_the_cultures_the_storage_shape_omits() -> None:
    """One line, two shapes: the board wants vessels, the store must not hold them."""
    repository = CultureRepository()
    line, culture = _introduce(repository)

    payload = line.to_payload(repository.cultures_of(line.id))

    assert payload["cultures"] == [culture.to_payload(line.replate_interval_days)]
    assert payload["id"] == line.id


def test_a_line_with_no_cultures_still_carries_the_key() -> None:
    """Empty rather than absent, so the card reads one shape."""
    line = CultureLine.introduced(
        _reference(), ReplateIntervals.from_payload(INTERVALS), now=A_TIME
    )

    assert line.to_payload()["cultures"] == []


def test_a_culture_decodes_from_what_it_encoded() -> None:
    """The storage shape is the one `from_dict` reads back."""
    repository = CultureRepository()
    _line, culture = _introduce(
        repository, plantlet_count=6, location="Shelf A", now=LATER
    )

    assert Culture.from_dict(culture.id, culture.to_dict()) == culture
