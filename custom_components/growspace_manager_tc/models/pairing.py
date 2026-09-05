"""A grower's endorsement of a phenotype on a Culture Medium, across versions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .common import optional_text, required_text
from .culture_line import PhenotypeReference


@dataclass(frozen=True, slots=True)
class Pairing:
    """One curated phenotype–medium association with an optional note."""

    id: str
    phenotype: PhenotypeReference
    medium_id: str
    notes: str
    created_at: str
    updated_at: str

    @classmethod
    def from_dict(cls, pairing_id: str, payload: Mapping[str, Any]) -> Pairing:
        """Decode a persisted endorsement without resolving foreign identity."""
        return cls(
            id=pairing_id,
            phenotype=PhenotypeReference.from_dict(payload.get("phenotype")),
            medium_id=required_text(payload.get("medium_id"), "Culture medium", 64),
            notes=optional_text(payload.get("notes"), "Notes", 4000),
            created_at=required_text(payload.get("created_at"), "Created at", 64),
            updated_at=required_text(payload.get("updated_at"), "Updated at", 64),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the shared storage and WebSocket shape."""
        return {
            "id": self.id,
            "phenotype": self.phenotype.to_dict(),
            "medium_id": self.medium_id,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
