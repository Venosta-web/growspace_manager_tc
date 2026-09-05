"""Data access repository for Growspace Manager TC."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
import logging
from typing import Any

from ..const import (
    COLLECTION_CULTURE_LINES,
    COLLECTION_CULTURE_MEDIA,
    COLLECTION_CULTURES,
    COLLECTION_MAINTENANCE_ACTIONS,
    COLLECTION_PAIRINGS,
)
from ..models.common import (
    TcConflictError,
    TcNotFoundError,
    TcValidationError,
    new_id,
    optional_text,
    required_text,
    utc_now_iso,
    whole_number,
)
from ..models.culture_line import (
    Culture,
    CultureLine,
    CultureStage,
    CultureStatus,
    PhenotypeReference,
    ReplateIntervals,
)
from ..models.culture_medium import CultureMedium, MediumFormulation
from ..models.maintenance import (
    DiscardReason,
    MaintenanceAction,
    MaintenanceActionType,
    ReplateVessel,
    note_text,
    requested_vessel,
    requested_vessels,
    required_note_text,
)
from ..models.pairing import Pairing

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class _Collection[T]:
    """One persisted collection, and whatever this version could not read.

    Every collection has the same three problems and they are worth solving
    once: a payload that is not a mapping at all, a record this version cannot
    decode, and the question of whether the collection key should be written
    back when it holds nothing.  Anything unreadable is held aside rather than
    dropped — it is invisible to the API, still on disk after the next save, and
    still counted in the manifest — so a store written by a newer version
    survives a load/save cycle instead of being silently emptied.
    """

    name: str
    records: dict[str, T] = field(default_factory=dict)
    unreadable: dict[str, Any] = field(default_factory=dict)
    readable: bool = True

    def load(self, raw: Any, decode: Callable[[str, Mapping[str, Any]], T]) -> Any:
        """Replace the records from persisted data.

        Returns whatever could not be indexed by ID at all, for the caller to
        put back where it came from — the collection then reads as empty rather
        than as something it is not.
        """
        self.records = {}
        self.unreadable = {}
        self.readable = True

        if not isinstance(raw, Mapping):
            _LOGGER.warning(
                "Persisted %s is not a collection and is left untouched", self.name
            )
            self.readable = False
            return raw

        for record_id, payload in raw.items():
            try:
                self.records[record_id] = decode(record_id, payload)
            except TcValidationError, AttributeError, TypeError:
                _LOGGER.warning(
                    "%s record %s could not be read and is left untouched",
                    self.name,
                    record_id,
                )
                self.unreadable[record_id] = payload
        return None

    def as_dict(self, encode: Callable[[T], dict[str, Any]]) -> dict[str, Any] | None:
        """Return the payload to persist, or None when there is nothing to write."""
        if not self.readable and not self.records:
            return None
        return {
            **{record_id: encode(record) for record_id, record in self.records.items()},
            **self.unreadable,
        }

    def claim(self) -> None:
        """Mark the collection this version's to write.

        A grower who adds a record has decided what this collection is; an
        unreadable blob cannot survive a real record being written over it.
        """
        self.readable = True


class CultureRepository:
    """Repository for tissue-culture records.

    Follows growspace_manager's repository pattern: the repository owns the
    in-memory collections and knows nothing about Home Assistant or about how
    they reach disk.  `StorageManager` loads them at setup and writes them back.

    Cultures live in their own collection rather than inside their line, so a
    Maintenance Action can write one Culture without rewriting the line it
    belongs to.  The board payload joins the two back together on the way out.

    Maintenance Actions are a third collection, and an append-only one: this
    class writes rows into it and has no method that edits or removes one.  The
    pairings collection holds curated phenotype–medium endorsements.
    Anything persisted that this version does not decode is kept verbatim and
    written back untouched.
    """

    def __init__(self) -> None:
        """Initialize an empty repository."""
        self._persisted: dict[str, Any] = {}
        self._media = _Collection[CultureMedium](COLLECTION_CULTURE_MEDIA)
        self._lines = _Collection[CultureLine](COLLECTION_CULTURE_LINES)
        self._cultures = _Collection[Culture](COLLECTION_CULTURES)
        self._actions = _Collection[MaintenanceAction](COLLECTION_MAINTENANCE_ACTIONS)
        self._pairings = _Collection[Pairing](COLLECTION_PAIRINGS)

    # -- persistence ------------------------------------------------------

    def load(self, data: Mapping[str, Any]) -> None:
        """Replace the collections from persisted data."""
        persisted = dict(data)
        raw = {
            collection.name: persisted.pop(collection.name, {})
            for collection in self._collections
        }
        self._persisted = persisted

        self._keep_unindexable(
            self._media,
            self._media.load(raw[self._media.name], CultureMedium.from_dict),
        )
        self._keep_unindexable(
            self._lines, self._lines.load(raw[self._lines.name], CultureLine.from_dict)
        )
        self._keep_unindexable(
            self._cultures,
            self._cultures.load(raw[self._cultures.name], Culture.from_dict),
        )
        self._keep_unindexable(
            self._actions,
            self._actions.load(raw[self._actions.name], MaintenanceAction.from_dict),
        )

        self._keep_unindexable(
            self._pairings,
            self._pairings.load(raw[self._pairings.name], Pairing.from_dict),
        )

    def _keep_unindexable(self, collection: _Collection[Any], raw: Any) -> None:
        """Put back a payload that could not be indexed by ID at all."""
        if raw is not None:
            self._persisted[collection.name] = raw

    def as_dict(self) -> dict[str, Any]:
        """Return the collections as the payload to persist."""
        payload = dict(self._persisted)
        for collection in self._collections:
            written = collection.as_dict(lambda record: record.to_dict())
            if written is not None:
                payload[collection.name] = written
        return payload

    def collection_sizes(self) -> dict[str, int]:
        """Return how many records each persisted collection holds.

        The manifest reports this, so the card can tell an empty install from a
        populated one without fetching any of it.  Collections appear as the V1
        model tickets land; anything persisted that is not a collection — a
        schema marker, a scalar setting — is left out rather than counted.
        """
        payload = self.as_dict()
        return {
            name: len(value)
            for name, value in payload.items()
            if isinstance(value, (dict, list))
        }

    @property
    def _collections(self) -> tuple[_Collection[Any], ...]:
        return (self._media, self._lines, self._cultures, self._actions, self._pairings)

    # -- culture media ----------------------------------------------------

    def culture_media(self) -> list[CultureMedium]:
        """Return the whole library, ordered the way it is shown."""
        return sorted(self._media.records.values(), key=lambda m: m.name.casefold())

    def culture_medium(self, medium_id: str) -> CultureMedium:
        """Return one Culture Medium, or raise `TcNotFoundError`."""
        medium = self._media.records.get(medium_id)
        if medium is None:
            raise TcNotFoundError(f"No culture medium with ID {medium_id}.")
        return medium

    def create_culture_medium(
        self, name: str, formulation: MediumFormulation, *, now: str | None = None
    ) -> CultureMedium:
        """Add a Culture Medium at version 1."""
        self._reject_duplicate_name(name, exclude_id=None)
        medium = CultureMedium.create(name, formulation, now=now or utc_now_iso())
        self._media.records[medium.id] = medium
        self._media.claim()
        return medium

    def update_culture_medium(
        self,
        medium_id: str,
        name: str,
        formulation: MediumFormulation,
        *,
        now: str | None = None,
    ) -> CultureMedium:
        """Apply an edit, forking a version if the formulation changed.

        Whether a version appears is `CultureMedium.edited`'s decision, not this
        one's — the repository only owns identity and the library-wide rules.
        """
        current = self.culture_medium(medium_id)
        self._reject_duplicate_name(name, exclude_id=medium_id)
        edited = current.edited(name, formulation, now=now or utc_now_iso())
        self._media.records[medium_id] = edited
        return edited

    def delete_culture_medium(self, medium_id: str) -> CultureMedium:
        """Remove a Culture Medium, and with it its version history.

        Nothing pins a Medium Version yet.  The Plating ticket owns the guard
        that has to stand here once something does: deleting a medium a Plating
        pinned would destroy the very record ADR-0004 exists to keep readable.
        """
        medium = self.culture_medium(medium_id)
        if any(pairing.medium_id == medium_id for pairing in self.pairings()):
            raise TcConflictError(
                "Remove this culture medium's pairings before deleting it."
            )
        del self._media.records[medium_id]
        return medium

    def _reject_duplicate_name(self, name: str, *, exclude_id: str | None) -> None:
        """Refuse a name another medium in the library already answers to.

        Case-insensitively: a library holding both "MS + BAP" and "ms + bap" is
        two rows nobody can tell apart, and a Pairing endorsing one of them
        would be unreadable.
        """
        key = name.casefold()
        for medium in self._media.records.values():
            if medium.id != exclude_id and medium.name.casefold() == key:
                raise TcConflictError(
                    f"A culture medium named “{medium.name}” already exists."
                )

    # -- culture lines and cultures ---------------------------------------

    def culture_lines(self) -> list[CultureLine]:
        """Return every line, ordered the way the board shows them.

        Live lines first and archived ones after, then by the phenotype name
        the reference snapshotted.  Sorting on the snapshot rather than on the
        resolved name is deliberate: the card resolves IDs client-side and TC
        cannot, so an ordering computed here has to use what TC holds — and a
        line whose phenotype was deleted keeps its place in the list instead of
        jumping to the end when it goes missing.
        """
        return sorted(
            self._lines.records.values(),
            key=lambda line: (
                line.archived,
                line.phenotype.name_snapshot.casefold(),
                line.created_at,
            ),
        )

    def culture_line(self, line_id: str) -> CultureLine:
        """Return one Culture Line, or raise `TcNotFoundError`."""
        line = self._lines.records.get(line_id)
        if line is None:
            raise TcNotFoundError(f"No culture line with ID {line_id}.")
        return line

    def cultures_of(self, line_id: str) -> tuple[Culture, ...]:
        """Return a line's Cultures, oldest first.

        Oldest first because that is the order they were created in, and a
        vessel's place on the board should not move when a newer one appears.
        """
        return tuple(
            sorted(
                (
                    culture
                    for culture in self._cultures.records.values()
                    if culture.line_id == line_id
                ),
                key=lambda culture: (culture.started_at, culture.id),
            )
        )

    def introduce_culture_line(
        self,
        phenotype: PhenotypeReference,
        intervals: ReplateIntervals,
        *,
        stage: Any = None,
        plantlet_count: Any = None,
        location: Any = None,
        now: str | None = None,
    ) -> tuple[CultureLine, Culture]:
        """Start a Culture Line and its first Culture in one act.

        One Introduction, one line, one first vessel — the two records are
        written together because a line with no Culture is a lineage nobody is
        keeping alive, and a caller that could produce one would eventually.
        """
        stamp = now or utc_now_iso()
        line = CultureLine.introduced(phenotype, intervals, now=stamp)
        culture = Culture.introduced(
            line.id,
            stage=stage,
            plantlet_count=plantlet_count,
            location=location,
            now=stamp,
        )
        self._lines.records[line.id] = line
        self._cultures.records[culture.id] = culture
        self._lines.claim()
        self._cultures.claim()
        return line, culture

    def relink_phenotype(
        self, line_id: str, phenotype: PhenotypeReference
    ) -> CultureLine:
        """Point a line at another phenotype, taking a fresh name snapshot.

        This is one of the two answers to a Missing Phenotype (ADR-0006); the
        other is `set_culture_line_archived`.  Neither deletes anything.
        """
        relinked = self.culture_line(line_id).relinked(phenotype)
        self._lines.records[line_id] = relinked
        return relinked

    def set_culture_line_archived(self, line_id: str, archived: bool) -> CultureLine:
        """Put a line away, or bring it back.

        Reversible on purpose: archiving is what a grower reaches for when a
        reference goes missing, and a one-way door there would make the honest
        move the frightening one.
        """
        updated = self.culture_line(line_id).with_archived(archived)
        self._lines.records[line_id] = updated
        return updated

    # -- maintenance actions ----------------------------------------------

    def culture(self, culture_id: str) -> Culture:
        """Return one Culture, or raise `TcNotFoundError`."""
        culture = self._cultures.records.get(culture_id)
        if culture is None:
            raise TcNotFoundError(f"No culture with ID {culture_id}.")
        return culture

    def maintenance_actions(
        self, *, culture_id: str | None = None, line_id: str | None = None
    ) -> list[MaintenanceAction]:
        """Return recorded acts, newest first.

        Newest first because that is the order the question is asked in — what
        happened to this vessel lately — and the record set is append-only, so
        the reverse of the order it was written in is exactly the reverse of
        the order it happened in.  Ties break on the ID, so two acts recorded
        in the same instant still order the same way on every read.
        """
        return sorted(
            (
                action
                for action in self._actions.records.values()
                if (culture_id is None or action.culture_id == culture_id)
                and (line_id is None or action.line_id == line_id)
            ),
            key=lambda action: (action.recorded_at, action.id),
            reverse=True,
        )

    def due_replates(self) -> list[tuple[CultureLine, Culture, str]]:
        """Return every Culture awaiting a Replate, soonest due first.

        Archived lines are left out: a line put away is not work, and a
        calendar that kept reminding a grower about vessels they archived is
        the reason they would stop trusting it.  A Culture with an unreadable
        anchor has no due date and is left out too, rather than being given an
        invented one.
        """
        due: list[tuple[CultureLine, Culture, str]] = []
        for line in self.culture_lines():
            if line.archived:
                continue
            for culture in self.cultures_of(line.id):
                stamp = culture.replate_due_at(line.replate_interval_days)
                if stamp is not None:
                    due.append((line, culture, stamp))
        return sorted(due, key=lambda entry: (entry[2], entry[1].id))

    def replate_culture(
        self,
        culture_id: str,
        medium_id: str,
        medium_version: Any,
        vessels: Any,
        *,
        note: Any = None,
        now: str | None = None,
    ) -> MaintenanceAction:
        """Transfer a Culture onto fresh medium, dividing it if asked.

        The first requested vessel is the Culture itself — its identity
        survives the transfer — and every further one is a new Culture on the
        same line at the same Stage.  The Medium Version is pinned on the act
        rather than on the vessel (ADR-0004): what a Pairing later reads is the
        placement, and a vessel replated three times has been on three of them.
        """
        culture = self._maintainable(culture_id)
        medium = self.culture_medium(medium_id)
        version = self._pinned_version(medium, medium_version)
        requested = requested_vessels(vessels)
        stamp = now or utc_now_iso()

        kept, extras = requested[0], requested[1:]
        count, location = requested_vessel(kept, culture.location)
        replated = culture.replated(plantlet_count=count, location=location, now=stamp)
        records = [replated]
        for entry in extras:
            count, location = requested_vessel(entry, culture.location)
            records.append(
                culture.divided(plantlet_count=count, location=location, now=stamp)
            )

        for record in records:
            self._cultures.records[record.id] = record
        self._cultures.claim()

        return self._record(
            MaintenanceAction.recorded(
                replated,
                MaintenanceActionType.REPLATE,
                note=note_text(note),
                medium_id=medium.id,
                medium_version=version,
                vessels=tuple(
                    ReplateVessel(
                        culture_id=record.id,
                        plantlet_count=record.plantlet_count,
                        location=record.location,
                    )
                    for record in records
                ),
                now=stamp,
            )
        )

    def discard_culture(
        self, culture_id: str, reason: Any, *, note: Any = None, now: str | None = None
    ) -> MaintenanceAction:
        """End a Culture with a reason. The vessel stays in history."""
        culture = self._maintainable(culture_id)
        discard_reason = _discard_reason(reason)
        self._cultures.records[culture.id] = culture.ended(CultureStatus.DISCARDED)
        return self._record(
            MaintenanceAction.recorded(
                culture,
                MaintenanceActionType.DISCARD,
                note=note_text(note),
                reason=discard_reason,
                now=now,
            )
        )

    def note_on_culture(
        self, culture_id: str, note: Any, *, now: str | None = None
    ) -> MaintenanceAction:
        """Record an observation against a Culture, changing nothing else.

        The note is required rather than optional here: an empty note is not an
        act, and recording one would put a row in the history that says nothing
        happened.
        """
        culture = self._maintainable(culture_id)
        return self._record(
            MaintenanceAction.recorded(
                culture,
                MaintenanceActionType.NOTE,
                note=required_note_text(note),
                now=now,
            )
        )

    def move_culture_to_rooting(
        self, culture_id: str, *, note: Any = None, now: str | None = None
    ) -> MaintenanceAction:
        """Move a Culture to the rooting Stage.

        Refused when it is already there.  A second move would record an act
        that changed nothing, and the history is the one place where that
        matters: a count of stage moves has to be a count of stage moves.
        """
        culture = self._maintainable(culture_id)
        if culture.stage is CultureStage.ROOTING:
            raise TcValidationError("That culture is already in rooting.")
        self._cultures.records[culture.id] = culture.moved_to_rooting()
        return self._record(
            MaintenanceAction.recorded(
                culture,
                MaintenanceActionType.MOVE_TO_ROOTING,
                note=note_text(note),
                stage=CultureStage.ROOTING,
                now=now,
            )
        )

    def graduate_culture(
        self, culture_id: str, *, note: Any = None, now: str | None = None
    ) -> MaintenanceAction:
        """End a Culture by taking it out of vitro.

        Persist this ending before attempting the optional service bridge.
        The bridge may complete its plant reference once; it cannot undo or
        repeat the graduation.
        """
        culture = self._maintainable(culture_id)
        note = note_text(note)
        self._cultures.records[culture.id] = culture.ended(CultureStatus.GRADUATED)
        return self._record(
            MaintenanceAction.recorded(
                culture,
                MaintenanceActionType.GRADUATE,
                note=note_text(note),
                now=now,
            )
        )

    def link_graduated_plant(self, action_id: str, plant_id: str) -> MaintenanceAction:
        """Complete a graduation's reference once, without rewriting its facts.

        This is the sole exception to immutable action fields: the ending is
        durable before GM runs, and the returned identity only exists afterwards.
        No public command allows a recorded link to be edited or retried.
        """
        action = self._actions.records[action_id]
        if (
            action.action is not MaintenanceActionType.GRADUATE
            or action.plant_id is not None
        ):
            raise TcValidationError("Only an unlinked graduation may receive a plant.")
        linked = replace(action, plant_id=required_text(plant_id, "Plant", 64))
        self._actions.records[action_id] = linked
        return linked

    def _maintainable(self, culture_id: str) -> Culture:
        """Return a Culture that can still be acted on, or refuse.

        Every Maintenance Action goes through here, so an ended vessel cannot
        be replated by one command and discarded twice by another — and the
        refusal is `validation_failed` rather than a not-found, because the
        board the grower is looking at is merely stale.
        """
        culture = self.culture(culture_id)
        if not culture.active:
            raise TcValidationError(
                f"That culture has already been {culture.status.value}."
            )
        return culture

    def _pinned_version(self, medium: CultureMedium, requested: Any) -> int:
        """Return the Medium Version a Replate pins, or refuse.

        A version outside the medium's history is a stale form rather than a
        wrong type — the grower had the medium open while someone else edited
        it — so it is named as a value to fix.
        """
        version = whole_number(requested, "Medium version", 1, 1_000_000)
        if not any(entry.version == version for entry in medium.versions):
            raise TcValidationError(
                f"“{medium.name}” has no version {version}; it is at version "
                f"{medium.current_version.version}."
            )
        return version

    def _record(self, action: MaintenanceAction) -> MaintenanceAction:
        """Append one act to the history.

        The only writer of that collection, and it only ever adds: there is no
        method here that edits or removes a Maintenance Action, because a
        history that could be rewritten would make every number derived from it
        — due dates, multiplication rates, the Plating trail — unreliable at
        once.
        """
        self._actions.records[action.id] = action
        self._actions.claim()
        return action

    # -- curated pairings -------------------------------------------------

    def pairings(self) -> list[Pairing]:
        """Return the single pairing set; both editor views project this list."""
        return sorted(self._pairings.records.values(), key=lambda row: row.id)

    def pairing(self, pairing_id: str) -> Pairing:
        """Return one endorsement or report a missing record."""
        pairing = self._pairings.records.get(pairing_id)
        if pairing is None:
            raise TcNotFoundError(f"No pairing with ID {pairing_id}.")
        return pairing

    def save_pairing(
        self,
        payload: Mapping[str, Any],
        *,
        pairing_id: str | None = None,
        now: str | None = None,
    ) -> Pairing:
        """Create or replace an endorsement, validating before any mutation.

        Updating can repair a missing phenotype or change the medium. The
        association remains unique even when its identity fields change.
        """
        current = self.pairing(pairing_id) if pairing_id is not None else None
        stamp = now or utc_now_iso()
        phenotype = PhenotypeReference.taken(
            payload.get("phenotype_id"), payload.get("phenotype_name"), now=stamp
        )
        medium_id = required_text(payload.get("medium_id"), "Culture medium", 64)
        self.culture_medium(medium_id)
        notes = optional_text(payload.get("notes"), "Notes", 4000)
        for row in self.pairings():
            if (
                row.id != pairing_id
                and row.phenotype.id == phenotype.id
                and row.medium_id == medium_id
            ):
                raise TcConflictError(
                    "This phenotype already has a pairing with this culture medium."
                )
        pairing = Pairing(
            id=current.id if current else new_id(),
            phenotype=(
                current.phenotype
                if current
                and current.phenotype.id == phenotype.id
                and current.phenotype.name_snapshot == phenotype.name_snapshot
                else phenotype
            ),
            medium_id=medium_id,
            notes=notes,
            created_at=current.created_at if current else stamp,
            updated_at=stamp,
        )
        self._pairings.records[pairing.id] = pairing
        self._pairings.claim()
        return pairing

    def delete_pairing(self, pairing_id: str) -> Pairing:
        """Remove an endorsement without changing either referenced entity."""
        pairing = self.pairing(pairing_id)
        del self._pairings.records[pairing_id]
        return pairing


def _discard_reason(value: Any) -> DiscardReason:
    """Return a Discard reason from the closed set, or raise."""
    try:
        return DiscardReason(value)
    except ValueError:
        allowed = ", ".join(member.value for member in DiscardReason)
        raise TcValidationError(f"Reason must be one of: {allowed}.") from None
