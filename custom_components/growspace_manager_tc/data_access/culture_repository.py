"""Data access repository for Growspace Manager TC."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class CultureRepository:
    """Repository for tissue-culture records.

    Follows growspace_manager's repository pattern: the repository owns the
    in-memory collections and knows nothing about Home Assistant or about how
    they reach disk.  `StorageManager` loads them at setup and writes them back.

    The V1 model tickets add the collections themselves — culture lines,
    cultures, media, pairings.  Until they land the repository holds none, so
    the only thing it does is round-trip whatever the store already contained.
    """

    def __init__(self) -> None:
        """Initialize an empty repository."""
        self._persisted: dict[str, Any] = {}

    def load(self, data: Mapping[str, Any]) -> None:
        """Replace the collections from persisted data.

        No collection is decoded yet, so the payload is kept verbatim.  That is
        deliberate: a store written by a newer version — a downgrade, a
        half-applied migration — survives a load/save cycle instead of being
        silently emptied by a version that does not understand it.
        """
        self._persisted = dict(data)

    def as_dict(self) -> dict[str, Any]:
        """Return the collections as the payload to persist."""
        return dict(self._persisted)
