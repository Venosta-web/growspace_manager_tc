"""Data access repository for Growspace Manager TC."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from ..const import COLLECTION_CULTURE_MEDIA
from ..models.culture_medium import (
    CultureMedium,
    MediumFormulation,
    MediumNameConflictError,
    MediumNotFoundError,
    MediumValidationError,
    utc_now_iso,
)

_LOGGER = logging.getLogger(__name__)


class CultureRepository:
    """Repository for tissue-culture records.

    Follows growspace_manager's repository pattern: the repository owns the
    in-memory collections and knows nothing about Home Assistant or about how
    they reach disk.  `StorageManager` loads them at setup and writes them back.

    The remaining V1 model tickets add the collections still missing — culture
    lines, cultures, platings, pairings.  Anything persisted that this version
    does not decode is kept verbatim and written back untouched, so a store
    written by a newer version — a downgrade, a half-applied migration —
    survives a load/save cycle instead of being silently emptied.
    """

    def __init__(self) -> None:
        """Initialize an empty repository."""
        self._persisted: dict[str, Any] = {}
        self._culture_media: dict[str, CultureMedium] = {}
        self._unreadable_media: dict[str, Any] = {}
        self._media_collection_readable = True

    # -- persistence ------------------------------------------------------

    def load(self, data: Mapping[str, Any]) -> None:
        """Replace the collections from persisted data."""
        persisted = dict(data)
        raw_media = persisted.pop(COLLECTION_CULTURE_MEDIA, {})
        self._persisted = persisted
        self._culture_media = {}
        self._unreadable_media = {}
        self._media_collection_readable = True

        if not isinstance(raw_media, Mapping):
            # Not a collection this version can index by ID at all.  Put it
            # back where it came from and hold no media: a load/save cycle then
            # leaves it exactly as its writer meant it, and the library reads
            # as empty rather than as something it is not.
            _LOGGER.warning(
                "Persisted %s is not a collection and is left untouched",
                COLLECTION_CULTURE_MEDIA,
            )
            self._persisted[COLLECTION_CULTURE_MEDIA] = raw_media
            self._media_collection_readable = False
            return

        for medium_id, payload in raw_media.items():
            try:
                self._culture_media[medium_id] = CultureMedium.from_dict(
                    medium_id, payload
                )
            except MediumValidationError, AttributeError, TypeError:
                # Not this version's shape.  Held aside rather than dropped:
                # the medium is invisible to the API, but it is still on disk
                # after the next save, and it still counts in the manifest.
                _LOGGER.warning(
                    "Culture medium %s could not be read and is left untouched",
                    medium_id,
                )
                self._unreadable_media[medium_id] = payload

    def as_dict(self) -> dict[str, Any]:
        """Return the collections as the payload to persist."""
        payload = dict(self._persisted)
        if self._media_collection_readable or self._culture_media:
            payload[COLLECTION_CULTURE_MEDIA] = {
                **{
                    medium_id: medium.to_dict()
                    for medium_id, medium in self._culture_media.items()
                },
                **self._unreadable_media,
            }
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

    # -- culture media ----------------------------------------------------

    def culture_media(self) -> list[CultureMedium]:
        """Return the whole library, ordered the way it is shown."""
        return sorted(self._culture_media.values(), key=lambda m: m.name.casefold())

    def culture_medium(self, medium_id: str) -> CultureMedium:
        """Return one Culture Medium, or raise `MediumNotFoundError`."""
        medium = self._culture_media.get(medium_id)
        if medium is None:
            raise MediumNotFoundError(f"No culture medium with ID {medium_id}.")
        return medium

    def create_culture_medium(
        self, name: str, formulation: MediumFormulation, *, now: str | None = None
    ) -> CultureMedium:
        """Add a Culture Medium at version 1."""
        self._reject_duplicate_name(name, exclude_id=None)
        medium = CultureMedium.create(name, formulation, now=now or utc_now_iso())
        self._culture_media[medium.id] = medium
        # A grower who adds a medium has decided what this collection is; an
        # unreadable blob cannot survive a real record being written over it.
        self._media_collection_readable = True
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
        self._culture_media[medium_id] = edited
        return edited

    def delete_culture_medium(self, medium_id: str) -> CultureMedium:
        """Remove a Culture Medium, and with it its version history.

        Nothing pins a Medium Version yet.  The Plating ticket owns the guard
        that has to stand here once something does: deleting a medium a Plating
        pinned would destroy the very record ADR-0004 exists to keep readable.
        """
        medium = self.culture_medium(medium_id)
        del self._culture_media[medium_id]
        return medium

    def _reject_duplicate_name(self, name: str, *, exclude_id: str | None) -> None:
        """Refuse a name another medium in the library already answers to.

        Case-insensitively: a library holding both "MS + BAP" and "ms + bap" is
        two rows nobody can tell apart, and a Pairing endorsing one of them
        would be unreadable.
        """
        key = name.casefold()
        for medium in self._culture_media.values():
            if medium.id != exclude_id and medium.name.casefold() == key:
                raise MediumNameConflictError(
                    f"A culture medium named “{medium.name}” already exists."
                )
