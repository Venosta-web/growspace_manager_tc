"""Tests for the Maintenance Actions, the history they write, and the due date."""

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
from custom_components.growspace_manager_tc.models.culture_medium import (
    CultureMedium,
    MediumFormulation,
)
from custom_components.growspace_manager_tc.models.maintenance import (
    MaintenanceAction,
    MaintenanceActionType,
)

INTERVALS: dict[str, Any] = {"multiplication": 30, "rooting": 21}
A_TIME = "2026-01-04T09:12:00+00:00"
LATER = "2026-02-18T16:40:00+00:00"
LATEST = "2026-03-30T08:05:00+00:00"
FORMULATION: dict[str, Any] = {
    "base_salts": "MS full strength",
    "additives": [],
    "hormones": [],
    "agar_g_per_l": 7.0,
    "sugar_g_per_l": 30.0,
    "ph_target": 5.8,
    "notes": "",
}


def _medium(repository: CultureRepository, name: str = "MS + BAP") -> CultureMedium:
    return repository.create_culture_medium(
        name, MediumFormulation.from_payload(FORMULATION), now=A_TIME
    )


def _introduce(
    repository: CultureRepository, **kwargs: Any
) -> tuple[CultureLine, Culture]:
    return repository.introduce_culture_line(
        PhenotypeReference.taken("Blue Dream|Pheno 2", "Blue Dream", now=A_TIME),
        ReplateIntervals.from_payload(kwargs.pop("intervals", None) or INTERVALS),
        now=kwargs.pop("now", A_TIME),
        **kwargs,
    )


def _bench() -> tuple[CultureRepository, CultureLine, Culture, CultureMedium]:
    """A repository holding one medium, one line and its first vessel."""
    repository = CultureRepository()
    medium = _medium(repository)
    line, culture = _introduce(repository, plantlet_count=6, location="Shelf A")
    return repository, line, culture, medium


def _replate(
    repository: CultureRepository,
    culture: Culture,
    medium: CultureMedium,
    vessels: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> MaintenanceAction:
    return repository.replate_culture(
        culture.id,
        medium.id,
        medium.current_version.version,
        vessels if vessels is not None else [{"plantlet_count": 5}],
        now=kwargs.pop("now", LATER),
        **kwargs,
    )


# -- the Replate Due Date ---------------------------------------------------


def test_the_due_date_is_the_anchor_plus_the_stage_interval() -> None:
    """The whole rule, and it is measured from the last Replate."""
    _repository, line, culture, _medium_record = _bench()

    assert culture.replate_due_at(line.replate_interval_days) == (
        "2026-02-03T09:12:00+00:00"
    )


def test_moving_to_rooting_changes_the_due_date_without_moving_the_anchor() -> None:
    """A stage move is not a plating: the same last Replate, a shorter interval."""
    repository, line, culture, _medium_record = _bench()

    repository.move_culture_to_rooting(culture.id, now=LATER)
    moved = repository.culture(culture.id)

    assert moved.last_replated_at == culture.last_replated_at
    assert moved.replate_due_at(line.replate_interval_days) == (
        "2026-01-25T09:12:00+00:00"
    )


@pytest.mark.parametrize("status", [CultureStatus.DISCARDED, CultureStatus.GRADUATED])
def test_an_ended_culture_is_never_due(status: CultureStatus) -> None:
    """A discarded or graduated vessel is not overdue, it is over."""
    _repository, line, culture, _medium_record = _bench()

    assert culture.ended(status).replate_due_at(line.replate_interval_days) is None


def test_an_unreadable_anchor_produces_no_due_date() -> None:
    """A date guessed from a stamp this version cannot read would be shown as fact."""
    _repository, line, culture, _medium_record = _bench()

    unreadable = Culture.from_dict(
        culture.id, {**culture.to_dict(), "last_replated_at": "whenever"}
    )

    assert unreadable.replate_due_at(line.replate_interval_days) is None


def test_the_wire_payload_carries_the_due_date_the_storage_shape_omits() -> None:
    """Derived, so it travels and is never persisted."""
    _repository, line, culture, _medium_record = _bench()

    assert "replate_due_at" not in culture.to_dict()
    assert culture.to_payload(line.replate_interval_days)["replate_due_at"] == (
        "2026-02-03T09:12:00+00:00"
    )


# -- replate ----------------------------------------------------------------


def test_a_replate_keeps_the_culture_and_resets_its_anchor() -> None:
    """Identity survives the transfer; only the anchor and the count move."""
    repository, _line, culture, medium = _bench()

    action = _replate(repository, culture, medium)
    replated = repository.culture(culture.id)

    assert action.action is MaintenanceActionType.REPLATE
    assert replated.id == culture.id
    assert replated.last_replated_at == LATER
    assert replated.plantlet_count == 5
    assert replated.location == "Shelf A"


def test_a_replate_pins_the_medium_version_it_was_poured_from() -> None:
    """What a Pairing later reads is the placement, not the medium's name."""
    repository, _line, culture, medium = _bench()

    action = _replate(repository, culture, medium)

    assert action.medium_id == medium.id
    assert action.medium_version == 1


def test_a_replate_divides_one_culture_into_several() -> None:
    """The first vessel is the culture; the rest are new ones on the same line."""
    repository, line, culture, medium = _bench()

    action = _replate(
        repository,
        culture,
        medium,
        [
            {"plantlet_count": 5, "location": "Shelf A"},
            {"plantlet_count": 4, "location": "Shelf B"},
        ],
    )

    assert [vessel.culture_id for vessel in action.vessels][0] == culture.id
    cultures = repository.cultures_of(line.id)
    assert len(cultures) == 2
    split_off = repository.culture(action.vessels[1].culture_id)
    assert split_off.line_id == line.id
    assert split_off.stage is culture.stage
    assert split_off.status is CultureStatus.ACTIVE
    assert split_off.started_at == LATER
    assert split_off.last_replated_at == LATER
    assert split_off.plantlet_count == 4
    assert split_off.location == "Shelf B"


def test_a_vessel_that_says_nothing_about_location_stays_where_it_was() -> None:
    """An absent location inherits; an empty one is the grower clearing it."""
    repository, _line, culture, medium = _bench()

    action = _replate(repository, culture, medium, [{}, {"location": ""}])

    assert repository.culture(culture.id).location == "Shelf A"
    assert repository.culture(action.vessels[1].culture_id).location == ""


def test_an_uncounted_replate_leaves_the_count_unknown() -> None:
    """After a division the old number describes something that no longer exists."""
    repository, _line, culture, medium = _bench()

    _replate(repository, culture, medium, [{}])

    assert repository.culture(culture.id).plantlet_count is None


def test_a_replate_needs_a_medium_that_exists() -> None:
    """A stale medium picker is a not-found, not a broken backend."""
    repository, _line, culture, _medium_record = _bench()

    with pytest.raises(TcNotFoundError):
        repository.replate_culture(culture.id, "nope", 1, [{}])


def test_a_replate_needs_a_version_that_medium_actually_has() -> None:
    """A version outside the history is a stale form the grower can fix."""
    repository, _line, culture, medium = _bench()

    with pytest.raises(TcValidationError, match="no version 4"):
        repository.replate_culture(culture.id, medium.id, 4, [{}])


@pytest.mark.parametrize(
    ("vessels", "message"),
    [
        ([], "at least one vessel"),
        ("two", "must be a list"),
        ([{}] * 51, "at most 50"),
        ([{"plantlet_count": -1}], "Plantlet count"),
        ([{"plantlet_count": 1.5}], "whole number"),
    ],
)
def test_a_replate_names_the_value_the_grower_has_to_fix(
    vessels: Any, message: str
) -> None:
    """Every rule about a division is a sentence, never a voluptuous dump."""
    repository, _line, culture, medium = _bench()

    with pytest.raises(TcValidationError, match=message):
        repository.replate_culture(
            culture.id, medium.id, medium.current_version.version, vessels
        )


# -- the endings, the note and the stage move -------------------------------


def test_a_discard_ends_the_culture_and_keeps_it() -> None:
    """A discarded vessel stays on the board, ended — it is not deleted."""
    repository, line, culture, _medium_record = _bench()

    action = repository.discard_culture(
        culture.id, "contamination", note="Bacterial haze.", now=LATER
    )

    assert action.reason is not None
    assert action.reason.value == "contamination"
    assert repository.culture(culture.id).status is CultureStatus.DISCARDED
    assert repository.cultures_of(line.id) == (repository.culture(culture.id),)


def test_a_discard_needs_a_reason_from_the_closed_set() -> None:
    """ "How much was lost to contamination" has to stay answerable."""
    repository, _line, culture, _medium_record = _bench()

    with pytest.raises(TcValidationError, match="contamination, spent, mistake"):
        repository.discard_culture(culture.id, "it went brown")


def test_a_graduation_is_recorded_as_a_plain_ending() -> None:
    """The bridge into Growspace Manager is its own ticket; the end is here."""
    repository, _line, culture, _medium_record = _bench()

    action = repository.graduate_culture(culture.id, note="Humidity dome.", now=LATER)

    assert action.action is MaintenanceActionType.GRADUATE
    assert repository.culture(culture.id).status is CultureStatus.GRADUATED


def test_a_note_changes_nothing_and_still_has_to_say_something() -> None:
    """An empty note is not an act."""
    repository, _line, culture, _medium_record = _bench()

    action = repository.note_on_culture(culture.id, "Looking good.", now=LATER)

    assert repository.culture(culture.id) == culture
    assert action.note == "Looking good."
    with pytest.raises(TcValidationError, match="Note is required"):
        repository.note_on_culture(culture.id, "   ")


def test_a_culture_cannot_be_moved_to_rooting_twice() -> None:
    """A count of stage moves has to be a count of stage moves."""
    repository, _line, culture, _medium_record = _bench()

    repository.move_culture_to_rooting(culture.id, now=LATER)

    assert repository.culture(culture.id).stage is CultureStage.ROOTING
    with pytest.raises(TcValidationError, match="already in rooting"):
        repository.move_culture_to_rooting(culture.id)


@pytest.mark.parametrize(
    "act",
    [
        lambda repository, culture, medium: _replate(repository, culture, medium),
        lambda repository, culture, medium: repository.discard_culture(
            culture.id, "spent"
        ),
        lambda repository, culture, medium: repository.note_on_culture(culture.id, "x"),
        lambda repository, culture, medium: repository.move_culture_to_rooting(
            culture.id
        ),
        lambda repository, culture, medium: repository.graduate_culture(culture.id),
    ],
)
def test_no_action_touches_a_culture_that_has_already_ended(act: Any) -> None:
    """One guard, so a stale board cannot discard a vessel twice."""
    repository, _line, culture, medium = _bench()
    repository.discard_culture(culture.id, "spent", now=LATER)

    with pytest.raises(TcValidationError, match="already been discarded"):
        act(repository, culture, medium)


def test_an_unknown_culture_is_not_found() -> None:
    """The card can tell a stale board from a broken backend."""
    repository = CultureRepository()

    with pytest.raises(TcNotFoundError):
        repository.note_on_culture("nope", "x")


# -- the history ------------------------------------------------------------


def test_the_history_is_newest_first_and_filterable() -> None:
    """The three questions: this vessel, this lineage, and what happened lately."""
    repository, line, culture, medium = _bench()
    _other_line, other_culture = _introduce(repository)

    _replate(repository, culture, medium)
    repository.note_on_culture(other_culture.id, "Other line.", now=A_TIME)

    assert [action.action.value for action in repository.maintenance_actions()] == [
        "replate",
        "note",
    ]
    assert [
        action.culture_id
        for action in repository.maintenance_actions(culture_id=culture.id)
    ] == [culture.id]
    assert [
        action.culture_id for action in repository.maintenance_actions(line_id=line.id)
    ] == [culture.id]


def test_the_history_is_append_only() -> None:
    """Nothing here edits or removes an act; a correction is another act."""
    repository, _line, culture, medium = _bench()

    _replate(repository, culture, medium)
    recorded = repository.maintenance_actions()
    repository.discard_culture(culture.id, "mistake", now=LATEST)

    assert repository.maintenance_actions()[1:] == recorded
    assert not [
        name
        for name in dir(repository)
        if name.startswith(("delete_maintenance", "update_maintenance"))
    ]


def test_an_act_decodes_from_what_it_encoded() -> None:
    """The storage shape is the one `from_dict` reads back."""
    repository, _line, culture, medium = _bench()

    action = _replate(
        repository, culture, medium, [{"plantlet_count": 5}, {"location": "Shelf B"}]
    )

    assert MaintenanceAction.from_dict(action.id, action.to_dict()) == action


def test_an_act_this_version_cannot_read_is_kept_and_counted() -> None:
    """A store written by a newer version survives a load/save cycle."""
    repository = CultureRepository()
    repository.load({"maintenance_actions": {"future-1": {"action": "sterilized"}}})

    assert repository.maintenance_actions() == []
    assert repository.as_dict()["maintenance_actions"] == {
        "future-1": {"action": "sterilized"}
    }
    assert repository.collection_sizes()["maintenance_actions"] == 1


# -- what the calendar reads ------------------------------------------------


def test_due_replates_skip_archived_lines_and_ended_vessels() -> None:
    """A line put away is not work, and an ended vessel is not late."""
    repository, line, culture, medium = _bench()
    archived_line, archived_culture = _introduce(repository, now=LATER)
    repository.set_culture_line_archived(archived_line.id, True)

    action = _replate(repository, culture, medium, [{}, {"location": "Shelf B"}])
    repository.discard_culture(action.vessels[1].culture_id, "spent", now=LATER)

    assert [entry[1].id for entry in repository.due_replates()] == [culture.id]
    assert archived_culture.id not in {
        entry[1].id for entry in repository.due_replates()
    }
    assert repository.due_replates()[0][2] == "2026-03-20T16:40:00+00:00"
    assert repository.due_replates()[0][0].id == line.id


def test_due_replates_are_ordered_soonest_first() -> None:
    """The most urgent work is the oldest outstanding, not the newest record."""
    repository = CultureRepository()
    _late_line, late = _introduce(repository, now=A_TIME)
    _soon_line, soon = _introduce(repository, now=LATER)

    assert [entry[1].id for entry in repository.due_replates()] == [late.id, soon.id]


# -- decoding what was persisted --------------------------------------------


def test_an_act_with_no_replate_fields_decodes_to_none() -> None:
    """The flat shape's null fields read back as null, not as missing keys."""
    repository, _line, culture, _medium_record = _bench()
    action = repository.note_on_culture(culture.id, "Looking good.", now=LATER)

    decoded = MaintenanceAction.from_dict(action.id, action.to_dict())

    assert decoded == action
    assert decoded.medium_id is None
    assert decoded.medium_version is None
    assert decoded.reason is None
    assert decoded.stage is None
    assert decoded.vessels == ()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"action": "sterilized"}, "Maintenance action must be one of"),
        ({"reason": "it went brown"}, "Reason must be one of"),
        ({"stage": "callus"}, "Culture stage must be one of"),
        ({"vessels": "one"}, "Vessels must be a list"),
        ({"vessels": ["one"]}, "vessel must be an object"),
    ],
)
def test_an_act_this_version_cannot_read_says_which_value_it_choked_on(
    payload: dict[str, Any], message: str
) -> None:
    """`_Collection` keeps the record aside; the sentence says why it had to."""
    repository, _line, culture, medium = _bench()
    encoded = _replate(repository, culture, medium).to_dict()

    with pytest.raises(TcValidationError, match=message):
        MaintenanceAction.from_dict("record-1", {**encoded, **payload})


def test_a_vessel_that_is_not_an_object_is_named_as_such() -> None:
    """The same sentence whether the list came off the wire or off disk."""
    repository, _line, culture, medium = _bench()

    with pytest.raises(TcValidationError, match="vessel must be an object"):
        repository.replate_culture(
            culture.id, medium.id, medium.current_version.version, ["Shelf A"]
        )


def test_graduation_link_is_completed_once_without_rewriting_the_ending() -> None:
    """Only a graduation can gain a link, and its original facts stay immutable."""
    repository, _line, culture, _medium_record = _bench()
    note = repository.note_on_culture(culture.id, "Healthy", now=A_TIME)
    with pytest.raises(TcValidationError, match="Only an unlinked graduation"):
        repository.link_graduated_plant(note.id, "plant-1")

    action = repository.graduate_culture(culture.id, note="Humidity dome.", now=LATER)
    linked = repository.link_graduated_plant(action.id, "plant-1")
    assert linked.to_dict() == {**action.to_dict(), "plant_id": "plant-1"}
    with pytest.raises(TcValidationError, match="Only an unlinked graduation"):
        repository.link_graduated_plant(action.id, "plant-2")
    assert repository.maintenance_actions()[0].plant_id == "plant-1"


def test_legacy_graduation_decodes_without_a_plant_reference() -> None:
    """Older stores keep their ending and acquire no invented link."""
    repository, _line, culture, _medium_record = _bench()
    action = repository.graduate_culture(culture.id, now=LATER)
    legacy = action.to_dict()
    del legacy["plant_id"]
    restored = MaintenanceAction.from_dict(action.id, legacy)
    assert restored == action
    assert restored.plant_id is None
