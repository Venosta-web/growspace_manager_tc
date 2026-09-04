"""Maintenance Actions — the closed vocabulary of acts recorded on a Culture.

Five acts and no more: Replate, Discard, note, move to rooting, and Graduation.
The set being closed is the point.  A free-text activity log would record the
same work and answer none of the questions this integration exists to answer —
what a vessel currently sits on, when it is next due, how many plantlets one
division produced — so every act is a typed record with the fields its own
question needs, and none of them is ever edited or removed.

**History is append-only.**  Nothing in this module returns a modified action,
because there is no such thing: a Culture's past is the sequence of actions
written against it, and an act that could be rewritten would make the Replate
Due Date, the Plantlet Count series and the Plating trail behind a Pairing all
unreliable at once.  A mistake is corrected by recording another act, which is
also how the grower already thinks about a bench.

Validation lives here rather than in the WebSocket schemas so the rules can be
argued with in a test that needs no Home Assistant, and so a value the grower
typed reaches the card as one `validation_failed` with a sentence in it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from .common import (
    TcValidationError,
    new_id,
    optional_text,
    required_text,
    utc_now_iso,
    whole_number,
)
from .culture_line import MAX_LOCATION_LENGTH, MAX_PLANTLET_COUNT, Culture, CultureStage

__all__ = [
    "DiscardReason",
    "MaintenanceAction",
    "MaintenanceActionType",
    "ReplateVessel",
    "new_action_id",
    "note_text",
    "requested_vessel",
    "requested_vessels",
    "required_note_text",
]

MAX_NOTE_LENGTH: Final = 2000

# One Replate divides one vessel; a hundred would be a card sending a loop by
# mistake rather than a grower dividing by hand.
MAX_REPLATE_VESSELS: Final = 50


class MaintenanceActionType(StrEnum):
    """The closed vocabulary of acts recorded on a Culture.

    A member here is a question the record set can answer later.  Adding one is
    a deliberate widening of that set — never a synonym for an act already in
    it, because two spellings of the same act make every count over the history
    wrong in a way nothing detects.
    """

    REPLATE = "replate"
    DISCARD = "discard"
    NOTE = "note"
    MOVE_TO_ROOTING = "move_to_rooting"
    GRADUATE = "graduate"


class DiscardReason(StrEnum):
    """Why a Culture was ended.

    Closed rather than free text, because "how much of this line was lost to
    contamination" is a question the history has to be able to answer.  The
    note beside it carries whatever the three words leave out.
    """

    CONTAMINATION = "contamination"
    SPENT = "spent"
    MISTAKE = "mistake"


def new_action_id() -> str:
    """Return an opaque identifier for a new Maintenance Action."""
    return new_id()


def _enum_member[T: StrEnum](enum: type[T], value: Any, field: str) -> T:
    """Return `value` as a member of `enum`, or raise."""
    try:
        return enum(value)
    except ValueError:
        allowed = ", ".join(member.value for member in enum)
        raise TcValidationError(f"{field} must be one of: {allowed}.") from None


def note_text(value: Any) -> str:
    """Return an optional note as it will be stored, or raise."""
    return optional_text(value, "Note", MAX_NOTE_LENGTH)


def required_note_text(value: Any) -> str:
    """Return a note that is the whole point of the act, or raise."""
    return required_text(value, "Note", MAX_NOTE_LENGTH)


def optional_plantlet_count(value: Any) -> int | None:
    """Return an optional Plantlet Count, or raise.

    `None` stays `None` rather than becoming 0: "nobody counted" and "the
    vessel is empty" are different facts, and a multiplication rate derived
    later can only trust counts that were really taken.
    """
    if value is None:
        return None
    return whole_number(value, "Plantlet count", 0, MAX_PLANTLET_COUNT)


@dataclass(frozen=True, slots=True)
class ReplateVessel:
    """One vessel a Replate produced, and what went into it.

    The first vessel of a Replate is the Culture that was replated — its
    identity survives the transfer (CONTEXT.md) — and every further vessel is a
    new Culture the division created.  Recording them as a list rather than as
    "the culture, plus some children" is what makes a division readable
    afterwards: the counts of all the vessels one act produced sit together, so
    a per-vessel multiplication rate is a subtraction rather than a
    reconstruction.

    `location` is `None` on the way in to mean "wherever it already was", and a
    string — possibly empty — to mean the grower said where.  Once recorded it
    is the plain text of the shelf the vessel went to.
    """

    culture_id: str
    plantlet_count: int | None
    location: str

    @classmethod
    def from_dict(cls, payload: Any) -> ReplateVessel:
        """Decode a persisted vessel."""
        if not isinstance(payload, Mapping):
            raise TcValidationError("Each vessel must be an object.")
        return cls(
            culture_id=required_text(payload.get("culture_id"), "Culture", 64),
            plantlet_count=optional_plantlet_count(payload.get("plantlet_count")),
            location=optional_text(
                payload.get("location"), "Location", MAX_LOCATION_LENGTH
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the wire and storage representation."""
        return {
            "culture_id": self.culture_id,
            "plantlet_count": self.plantlet_count,
            "location": self.location,
        }


def requested_vessels(payload: Any) -> list[Any]:
    """Return the vessels a Replate asked for, or raise.

    At least one, because a Replate always puts the Culture somewhere; the
    extras are the division.
    """
    if isinstance(payload, (str, bytes)) or not isinstance(payload, Sequence):
        raise TcValidationError("Vessels must be a list.")
    if not payload:
        raise TcValidationError("A replate needs at least one vessel.")
    if len(payload) > MAX_REPLATE_VESSELS:
        raise TcValidationError(
            f"A replate may divide into at most {MAX_REPLATE_VESSELS} vessels."
        )
    return list(payload)


def requested_vessel(payload: Any, inherited: str) -> tuple[int | None, str]:
    """Validate one requested vessel into the two values it carries.

    Returned as a pair rather than as a `ReplateVessel` because the vessel's
    Culture does not exist yet when a division is being validated — the record
    is written once the Culture it names has an ID.

    An absent `location` means "wherever it already was" and inherits; an empty
    string means the grower cleared it.  Collapsing the two would make a form
    that submits blank fields quietly wipe every shelf label on the board.
    """
    if not isinstance(payload, Mapping):
        raise TcValidationError("Each vessel must be an object.")
    location = payload.get("location")
    return (
        optional_plantlet_count(payload.get("plantlet_count")),
        inherited
        if location is None
        else optional_text(location, "Location", MAX_LOCATION_LENGTH),
    )


@dataclass(frozen=True, slots=True)
class MaintenanceAction:
    """One recorded act on one Culture.

    Flat rather than a union of five shapes, and every field always present:
    the card reads one schema, a persisted record decodes without knowing which
    act it is first, and a reader counting replates never has to guess whether
    a missing key means "not applicable" or "an older version did not write
    it".  The fields an act does not use are `null` or empty.

    `line_id` is denormalized from the Culture on purpose.  A line's whole
    history has to stay readable after the vessels it happened in have ended,
    and a join through a Culture that a later version might store differently
    is a worse bet than the ID the act was recorded against.
    """

    id: str
    culture_id: str
    line_id: str
    action: MaintenanceActionType
    recorded_at: str
    note: str
    # Replate only: the Medium Version this placement pinned (ADR-0004), and
    # every vessel the act produced.
    medium_id: str | None
    medium_version: int | None
    vessels: tuple[ReplateVessel, ...]
    # Discard only.
    reason: DiscardReason | None
    # Move to rooting only: the stage the Culture was moved to, so a reader
    # need not know that today only one move exists.
    stage: CultureStage | None

    @classmethod
    def recorded(
        cls,
        culture: Culture,
        action: MaintenanceActionType,
        *,
        note: str = "",
        medium_id: str | None = None,
        medium_version: int | None = None,
        vessels: tuple[ReplateVessel, ...] = (),
        reason: DiscardReason | None = None,
        stage: CultureStage | None = None,
        now: str | None = None,
    ) -> MaintenanceAction:
        """Write one act against a Culture."""
        return cls(
            id=new_action_id(),
            culture_id=culture.id,
            line_id=culture.line_id,
            action=action,
            recorded_at=now or utc_now_iso(),
            note=note,
            medium_id=medium_id,
            medium_version=medium_version,
            vessels=vessels,
            reason=reason,
            stage=stage,
        )

    @classmethod
    def from_dict(cls, action_id: str, payload: Mapping[str, Any]) -> MaintenanceAction:
        """Decode a persisted act."""
        raw_vessels = payload.get("vessels") or ()
        if isinstance(raw_vessels, (str, bytes)) or not isinstance(
            raw_vessels, Sequence
        ):
            raise TcValidationError("Vessels must be a list.")
        reason = payload.get("reason")
        stage = payload.get("stage")
        return cls(
            id=action_id,
            culture_id=required_text(payload.get("culture_id"), "Culture", 64),
            line_id=required_text(payload.get("line_id"), "Culture line", 64),
            action=_enum_member(
                MaintenanceActionType, payload.get("action"), "Maintenance action"
            ),
            recorded_at=required_text(payload.get("recorded_at"), "Recorded at", 64),
            note=note_text(payload.get("note")),
            medium_id=_optional_id(payload.get("medium_id")),
            medium_version=_optional_version(payload.get("medium_version")),
            vessels=tuple(ReplateVessel.from_dict(entry) for entry in raw_vessels),
            reason=(
                None
                if reason is None
                else _enum_member(DiscardReason, reason, "Reason")
            ),
            stage=(
                None
                if stage is None
                else _enum_member(CultureStage, stage, "Culture stage")
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the wire and storage representation."""
        return {
            "id": self.id,
            "culture_id": self.culture_id,
            "line_id": self.line_id,
            "action": self.action.value,
            "recorded_at": self.recorded_at,
            "note": self.note,
            "medium_id": self.medium_id,
            "medium_version": self.medium_version,
            "vessels": [vessel.to_dict() for vessel in self.vessels],
            "reason": None if self.reason is None else self.reason.value,
            "stage": None if self.stage is None else self.stage.value,
        }


def _optional_id(value: Any) -> str | None:
    """Return an optional opaque identifier, or raise."""
    if value is None:
        return None
    return required_text(value, "Culture medium", 64)


def _optional_version(value: Any) -> int | None:
    """Return an optional Medium Version number, or raise."""
    if value is None:
        return None
    return whole_number(value, "Medium version", 1, 1_000_000)
