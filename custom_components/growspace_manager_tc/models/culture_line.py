"""Culture Lines, their Cultures, and the Phenotype Reference a line is started from.

A **Culture Line** is one preserved in-vitro lineage of one phenotype, started
by a single **Introduction**.  A **Culture** is one plantlet group in one
vessel; a line owns however many of them the Replates have produced.

The load-bearing decision in this module is the **Phenotype Reference**.
Growspace Manager owns phenotype identity (ADR-0002), so a line stores an
opaque ID and nothing else that identifies the phenotype — except a
display-name snapshot taken at reference time (ADR-0006).  The ID stays the
only authority for identity and joins; the snapshot exists so that a phenotype
deleted in Growspace Manager renders as a named Missing Phenotype rather than
vanishing.  Nothing here resolves an ID: TC cannot, and the card does the join
client-side.

Validation lives here rather than in the WebSocket schemas so the rules can be
argued with in a test that needs no Home Assistant, and so that a value the
grower typed reaches the card as one `validation_failed` with a sentence in it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
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

__all__ = [
    "Culture",
    "CultureLine",
    "CultureStage",
    "CultureStatus",
    "PhenotypeReference",
    "ReplateIntervals",
    "new_culture_id",
    "new_line_id",
]

# Generous, and there to catch a paste rather than to have an opinion.  A
# phenotype ID is Growspace Manager's to shape, so the only rule about it here
# is that it is non-empty text short enough to store.
MAX_PHENOTYPE_ID_LENGTH: Final = 255
MAX_PHENOTYPE_NAME_LENGTH: Final = 255
MAX_LOCATION_LENGTH: Final = 120

# An interval is in days, and both ends are a unit slip rather than a recipe:
# nobody replates twice a day, and a line whose interval is longer than a year
# is not being maintained.
MIN_INTERVAL_DAYS: Final = 1
MAX_INTERVAL_DAYS: Final = 365
MAX_PLANTLET_COUNT: Final = 10_000


class CultureStage(StrEnum):
    """Whether a Culture is multiplying or being rooted.

    The stage is what selects which of the line's replate intervals applies, so
    it is a closed set: a third spelling would be an interval nobody defined.
    """

    MULTIPLICATION = "multiplication"
    ROOTING = "rooting"


class CultureStatus(StrEnum):
    """Where a Culture stands.

    `ACTIVE` is the only status an Introduction can produce.  The other two are
    ends, written by the Maintenance Actions that own them — a Culture is never
    deleted, so history stays computable (CONTEXT.md).
    """

    ACTIVE = "active"
    DISCARDED = "discarded"
    GRADUATED = "graduated"


def new_line_id() -> str:
    """Return an opaque identifier for a new Culture Line."""
    return new_id()


def new_culture_id() -> str:
    """Return an opaque identifier for a new Culture."""
    return new_id()


def _enum_member[T: StrEnum](
    enum: type[T], value: Any, field: str, default: T | None = None
) -> T:
    """Return `value` as a member of `enum`, or raise."""
    if value is None and default is not None:
        return default
    try:
        return enum(value)
    except ValueError:
        allowed = ", ".join(member.value for member in enum)
        raise TcValidationError(f"{field} must be one of: {allowed}.") from None


@dataclass(frozen=True, slots=True)
class PhenotypeReference:
    """An opaque phenotype ID, with the display name it had when it was taken.

    `id` is Growspace Manager's, and this integration never parses it — a
    composite key today is an opaque string here, and stays one if Growspace
    Manager reshapes it.  `name_snapshot` is a display fallback and not a second
    source of truth: when the ID still resolves, the card shows Growspace
    Manager's current name and this value is never seen.
    """

    id: str
    name_snapshot: str
    snapshot_at: str

    @classmethod
    def taken(
        cls, phenotype_id: Any, phenotype_name: Any, *, now: str | None = None
    ) -> PhenotypeReference:
        """Take a reference to a phenotype, stamping the name as it reads now."""
        return cls(
            id=required_text(phenotype_id, "Phenotype", MAX_PHENOTYPE_ID_LENGTH),
            name_snapshot=required_text(
                phenotype_name, "Phenotype name", MAX_PHENOTYPE_NAME_LENGTH
            ),
            snapshot_at=now or utc_now_iso(),
        )

    @classmethod
    def from_dict(cls, payload: Any) -> PhenotypeReference:
        """Decode a persisted reference."""
        if not isinstance(payload, Mapping):
            raise TcValidationError("A culture line must carry a phenotype reference.")
        return cls(
            id=required_text(payload.get("id"), "Phenotype", MAX_PHENOTYPE_ID_LENGTH),
            name_snapshot=required_text(
                payload.get("name_snapshot"),
                "Phenotype name",
                MAX_PHENOTYPE_NAME_LENGTH,
            ),
            snapshot_at=required_text(payload.get("snapshot_at"), "Snapshot at", 64),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the wire and storage representation."""
        return {
            "id": self.id,
            "name_snapshot": self.name_snapshot,
            "snapshot_at": self.snapshot_at,
        }


@dataclass(frozen=True, slots=True)
class ReplateIntervals:
    """How many days a Culture may sit on one medium, per Culture Stage.

    Both stages are required rather than defaulted, because the number is the
    grower's protocol and a silent default would produce a Replate Due Date
    that looks authoritative and is invented.  Keyed by stage so that adding a
    stage later is one enum member and one field, not a new column everywhere.
    """

    multiplication: int
    rooting: int

    @classmethod
    def from_payload(cls, payload: Any) -> ReplateIntervals:
        """Validate the per-stage intervals from the wire or the store."""
        if not isinstance(payload, Mapping):
            raise TcValidationError(
                "Replate intervals must be given for every culture stage."
            )
        return cls(
            multiplication=whole_number(
                payload.get(CultureStage.MULTIPLICATION.value),
                "Multiplication interval",
                MIN_INTERVAL_DAYS,
                MAX_INTERVAL_DAYS,
            ),
            rooting=whole_number(
                payload.get(CultureStage.ROOTING.value),
                "Rooting interval",
                MIN_INTERVAL_DAYS,
                MAX_INTERVAL_DAYS,
            ),
        )

    def for_stage(self, stage: CultureStage) -> int:
        """Return the interval that applies to a Culture at `stage`."""
        return (
            self.multiplication
            if stage is CultureStage.MULTIPLICATION
            else self.rooting
        )

    def to_dict(self) -> dict[str, int]:
        """Return the wire and storage representation."""
        return {
            CultureStage.MULTIPLICATION.value: self.multiplication,
            CultureStage.ROOTING.value: self.rooting,
        }


@dataclass(frozen=True, slots=True)
class Culture:
    """One plantlet group in one vessel, belonging to one Culture Line.

    `last_replated_at` is the anchor the line's interval is measured from, and
    an Introduction sets it: placing the explant *is* a plating onto fresh
    medium, so a culture is never without an anchor and the worklist never has
    to guess one.  `plantlet_count` is optional and stays `None` rather than
    becoming 0 — "nobody counted" and "the vessel is empty" are different
    facts, and a per-vessel multiplication rate can only be derived later from
    counts that were really taken.
    """

    id: str
    line_id: str
    stage: CultureStage
    status: CultureStatus
    started_at: str
    last_replated_at: str
    plantlet_count: int | None
    location: str

    @classmethod
    def introduced(
        cls,
        line_id: str,
        *,
        stage: Any = None,
        plantlet_count: Any = None,
        location: Any = None,
        now: str | None = None,
    ) -> Culture:
        """Start the first Culture of a line."""
        started_at = now or utc_now_iso()
        return cls(
            id=new_culture_id(),
            line_id=line_id,
            stage=_enum_member(
                CultureStage, stage, "Culture stage", CultureStage.MULTIPLICATION
            ),
            status=CultureStatus.ACTIVE,
            started_at=started_at,
            last_replated_at=started_at,
            plantlet_count=_plantlet_count(plantlet_count),
            location=optional_text(location, "Location", MAX_LOCATION_LENGTH),
        )

    @classmethod
    def from_dict(cls, culture_id: str, payload: Mapping[str, Any]) -> Culture:
        """Decode a persisted culture."""
        started_at = required_text(payload.get("started_at"), "Started at", 64)
        return cls(
            id=culture_id,
            line_id=required_text(payload.get("line_id"), "Culture line", 64),
            stage=_enum_member(CultureStage, payload.get("stage"), "Culture stage"),
            status=_enum_member(CultureStatus, payload.get("status"), "Culture status"),
            started_at=started_at,
            last_replated_at=optional_text(
                payload.get("last_replated_at"), "Last replated at", 64
            )
            or started_at,
            plantlet_count=_plantlet_count(payload.get("plantlet_count")),
            location=optional_text(
                payload.get("location"), "Location", MAX_LOCATION_LENGTH
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the wire and storage representation."""
        return {
            "id": self.id,
            "line_id": self.line_id,
            "stage": self.stage.value,
            "status": self.status.value,
            "started_at": self.started_at,
            "last_replated_at": self.last_replated_at,
            "plantlet_count": self.plantlet_count,
            "location": self.location,
        }


def _plantlet_count(value: Any) -> int | None:
    """Return an optional plantlet count, or raise."""
    if value is None:
        return None
    return whole_number(value, "Plantlet count", 0, MAX_PLANTLET_COUNT)


@dataclass(frozen=True, slots=True)
class CultureLine:
    """One preserved lineage of one phenotype, and how often it is replated.

    A line owns the Phenotype Reference and the intervals; its Cultures are
    stored beside it rather than inside it, because a Maintenance Action acts on
    a Culture and would otherwise have to rewrite the whole line to record one.

    `archived_at` is the other half of the Missing Phenotype answer (ADR-0006):
    a line whose phenotype no longer resolves can be re-linked to another one or
    put away, and archiving keeps it — with its history — rather than deleting
    it.
    """

    id: str
    phenotype: PhenotypeReference
    replate_interval_days: ReplateIntervals
    created_at: str
    updated_at: str
    archived_at: str | None

    @property
    def archived(self) -> bool:
        """Whether this line has been put away."""
        return self.archived_at is not None

    @classmethod
    def introduced(
        cls,
        phenotype: PhenotypeReference,
        intervals: ReplateIntervals,
        *,
        now: str | None = None,
    ) -> CultureLine:
        """Start a line from an Introduction."""
        created_at = now or utc_now_iso()
        return cls(
            id=new_line_id(),
            phenotype=phenotype,
            replate_interval_days=intervals,
            created_at=created_at,
            updated_at=created_at,
            archived_at=None,
        )

    def relinked(
        self, phenotype: PhenotypeReference, *, now: str | None = None
    ) -> CultureLine:
        """Return this line pointed at another phenotype, snapshot and all.

        Re-linking replaces the whole reference rather than only the ID: the
        snapshot is the name of *this* phenotype, and keeping the old one would
        leave a line that renders under a name it no longer refers to.
        """
        return replace(self, phenotype=phenotype, updated_at=now or utc_now_iso())

    def with_archived(self, archived: bool, *, now: str | None = None) -> CultureLine:
        """Return this line put away, or brought back.

        Re-archiving an archived line keeps the stamp it already carries: the
        interesting date is when it was put away, not when someone last pressed
        the button.
        """
        if archived == self.archived:
            return self
        stamp = now or utc_now_iso()
        return replace(self, archived_at=stamp if archived else None, updated_at=stamp)

    @classmethod
    def from_dict(cls, line_id: str, payload: Mapping[str, Any]) -> CultureLine:
        """Decode a persisted line."""
        created_at = required_text(payload.get("created_at"), "Created at", 64)
        return cls(
            id=line_id,
            phenotype=PhenotypeReference.from_dict(payload.get("phenotype")),
            replate_interval_days=ReplateIntervals.from_payload(
                payload.get("replate_interval_days")
            ),
            created_at=created_at,
            updated_at=optional_text(payload.get("updated_at"), "Updated at", 64)
            or created_at,
            archived_at=optional_text(payload.get("archived_at"), "Archived at", 64)
            or None,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the storage representation — the line alone."""
        return {
            "id": self.id,
            "phenotype": self.phenotype.to_dict(),
            "replate_interval_days": self.replate_interval_days.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "archived_at": self.archived_at,
        }

    def to_payload(self, cultures: tuple[Culture, ...] = ()) -> dict[str, Any]:
        """Return the wire representation — the line with its vessels.

        The board wants a line and its Cultures in one payload; persistence
        keeps them in separate collections, because a Maintenance Action writes
        one Culture and must not rewrite its line to do it.  `cultures` is
        always present, empty rather than absent, so a line whose every Culture
        has ended reads the same shape as one that never had any.
        """
        return {
            **self.to_dict(),
            "cultures": [culture.to_dict() for culture in cultures],
        }
