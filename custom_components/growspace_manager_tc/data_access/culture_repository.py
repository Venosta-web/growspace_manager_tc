"""Data access repository for Growspace Manager TC."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
import logging
from typing import Any

from ..const import (
    COLLECTION_CULTURE_LINES,
    COLLECTION_CULTURE_MEDIA,
    COLLECTION_CULTURES,
)
from ..models.common import (
    TcConflictError,
    TcNotFoundError,
    TcValidationError,
    utc_now_iso,
)
from ..models.culture_line import (
    Culture,
    CultureLine,
    PhenotypeReference,
    ReplateIntervals,
)
from ..models.culture_medium import CultureMedium, MediumFormulation

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

    The remaining V1 model tickets add the collections still missing — platings
    and pairings.  Anything persisted that this version does not decode is kept
    verbatim and written back untouched.
    """

    def __init__(self) -> None:
        """Initialize an empty repository."""
        self._persisted: dict[str, Any] = {}
        self._media = _Collection[CultureMedium](COLLECTION_CULTURE_MEDIA)
        self._lines = _Collection[CultureLine](COLLECTION_CULTURE_LINES)
        self._cultures = _Collection[Culture](COLLECTION_CULTURES)

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
        return (self._media, self._lines, self._cultures)

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
