"""Culture Media and their immutable Medium Versions.

A Culture Medium is a named formulation Cultures grow on; a Medium Version is an
immutable snapshot of that formulation, and every future Plating pins one
(ADR-0004).  So the interesting rule in this module is not what a medium holds
but when a new version appears: **a version is minted by a change to the
formulation, never by the act of saving.**  Re-saving an unchanged form adds
nothing to the history, and renaming a medium adds nothing either — the name is
the library's label for the lineage, not part of the snapshot a Plating pins.

Validation lives here rather than in the WebSocket schemas so that the rules can
be tested without Home Assistant, and so that every rejection reaches the card
as one `validation_failed` with a sentence in it instead of a voluptuous dump.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Final

from .common import (
    TcValidationError,
    new_id,
    number as _number,
    optional_text as _optional_text,
    required_text as _required_text,
    utc_now_iso,
)

__all__ = [
    "CultureMedium",
    "MediumComponent",
    "MediumFormulation",
    "MediumVersion",
    "new_medium_id",
    "validate_medium_name",
]

# Field limits.  These are deliberately generous — they exist to catch a unit
# slip (grams typed where milligrams were meant, a pH of 58) rather than to have
# an opinion about anyone's recipe.
MAX_NAME_LENGTH: Final = 120
MAX_NOTES_LENGTH: Final = 2000
MAX_COMPONENTS: Final = 40
MAX_AGAR_G_PER_L: Final = 30.0
MAX_SUGAR_G_PER_L: Final = 100.0
MAX_COMPONENT_AMOUNT: Final = 100_000.0
MIN_PH: Final = 3.0
MAX_PH: Final = 9.0


def new_medium_id() -> str:
    """Return an opaque identifier for a new Culture Medium."""
    return new_id()


def validate_medium_name(value: Any) -> str:
    """Return a Culture Medium's name as it will be stored, or raise."""
    return _required_text(value, "Name", MAX_NAME_LENGTH)


@dataclass(frozen=True, slots=True)
class MediumComponent:
    """One additive or hormone entry, with its concentration.

    The unit is free text on purpose: hormones are dosed in mg/L by some growers
    and µM by others, and a closed vocabulary would either be wrong for half of
    them or grow a conversion table this integration has no business owning.
    """

    name: str
    amount: float
    unit: str

    @classmethod
    def from_payload(cls, payload: Any, field: str) -> MediumComponent:
        """Validate one entry from the wire or the store."""
        if not isinstance(payload, Mapping):
            raise TcValidationError(f"Each {field} entry must be an object.")
        return cls(
            name=_required_text(payload.get("name"), f"{field} name", MAX_NAME_LENGTH),
            amount=_number(
                payload.get("amount"), f"{field} amount", 0.0, MAX_COMPONENT_AMOUNT
            ),
            unit=_required_text(payload.get("unit"), f"{field} unit", MAX_NAME_LENGTH),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the wire and storage representation."""
        return {"name": self.name, "amount": self.amount, "unit": self.unit}


def _components(payload: Any, field: str) -> tuple[MediumComponent, ...]:
    """Validate a list of additive or hormone entries."""
    if payload is None:
        return ()
    if isinstance(payload, (str, bytes)) or not isinstance(payload, Sequence):
        raise TcValidationError(f"{field} must be a list.")
    if len(payload) > MAX_COMPONENTS:
        raise TcValidationError(f"{field} may hold at most {MAX_COMPONENTS} entries.")

    components = tuple(MediumComponent.from_payload(entry, field) for entry in payload)
    seen: set[str] = set()
    for component in components:
        key = component.name.casefold()
        if key in seen:
            raise TcValidationError(
                f"{field} lists “{component.name}” twice; give it one entry."
            )
        seen.add(key)
    return components


@dataclass(frozen=True, slots=True)
class MediumFormulation:
    """The part of a Culture Medium that a Medium Version snapshots.

    Everything here is pinned by a Plating; the medium's name and identity are
    not, which is why they live on `CultureMedium` instead.
    """

    base_salts: str
    additives: tuple[MediumComponent, ...]
    hormones: tuple[MediumComponent, ...]
    agar_g_per_l: float
    sugar_g_per_l: float
    ph_target: float
    notes: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> MediumFormulation:
        """Validate a formulation from the wire or the store."""
        return cls(
            base_salts=_required_text(
                payload.get("base_salts"), "Base salts", MAX_NAME_LENGTH
            ),
            additives=_components(payload.get("additives"), "Additive"),
            hormones=_components(payload.get("hormones"), "Hormone"),
            agar_g_per_l=_number(
                payload.get("agar_g_per_l"), "Agar", 0.0, MAX_AGAR_G_PER_L
            ),
            sugar_g_per_l=_number(
                payload.get("sugar_g_per_l"), "Sugar", 0.0, MAX_SUGAR_G_PER_L
            ),
            ph_target=_number(payload.get("ph_target"), "pH target", MIN_PH, MAX_PH),
            notes=_optional_text(payload.get("notes"), "Notes", MAX_NOTES_LENGTH),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the wire and storage representation."""
        return {
            "base_salts": self.base_salts,
            "additives": [component.to_dict() for component in self.additives],
            "hormones": [component.to_dict() for component in self.hormones],
            "agar_g_per_l": self.agar_g_per_l,
            "sugar_g_per_l": self.sugar_g_per_l,
            "ph_target": self.ph_target,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class MediumVersion:
    """An immutable snapshot of a Culture Medium's formulation.

    Frozen because the point of the type is that nothing rewrites it: a Plating
    that pinned version 2 must still describe what was actually poured, however
    many times the medium has been edited since.
    """

    version: int
    created_at: str
    formulation: MediumFormulation

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> MediumVersion:
        """Decode a persisted version."""
        version = payload.get("version")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise TcValidationError("Version number must be a positive integer.")
        return cls(
            version=version,
            created_at=_required_text(payload.get("created_at"), "Created at", 64),
            formulation=MediumFormulation.from_payload(payload),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the wire and storage representation.

        The formulation is flattened into the version rather than nested: a
        version *is* a formulation plus when it was taken, and the card renders
        one row per version out of exactly these keys.
        """
        return {
            "version": self.version,
            "created_at": self.created_at,
            **self.formulation.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class CultureMedium:
    """A named Culture Medium and the whole history of its formulation.

    `versions` is ordered oldest first and only ever grows.  The newest entry is
    what a fresh Plating would pin; the rest are kept because older Platings
    already pinned them.
    """

    id: str
    name: str
    created_at: str
    updated_at: str
    versions: tuple[MediumVersion, ...]

    @property
    def current_version(self) -> MediumVersion:
        """Return the version a new Plating would pin."""
        return self.versions[-1]

    @classmethod
    def create(
        cls, name: str, formulation: MediumFormulation, *, now: str | None = None
    ) -> CultureMedium:
        """Start a medium at version 1."""
        created_at = now or utc_now_iso()
        return cls(
            id=new_medium_id(),
            name=name,
            created_at=created_at,
            updated_at=created_at,
            versions=(
                MediumVersion(
                    version=1, created_at=created_at, formulation=formulation
                ),
            ),
        )

    def edited(
        self, name: str, formulation: MediumFormulation, *, now: str | None = None
    ) -> CultureMedium:
        """Return this medium with the edit applied.

        Forks a new version when the formulation actually changed, and only
        then.  A rename, or a save that changed nothing, leaves the history
        exactly as it was — an immutable history is only readable if it records
        edits rather than keystrokes.
        """
        edited_at = now or utc_now_iso()
        if formulation == self.current_version.formulation:
            if name == self.name:
                return self
            return replace(self, name=name, updated_at=edited_at)

        version = MediumVersion(
            version=self.current_version.version + 1,
            created_at=edited_at,
            formulation=formulation,
        )
        return replace(
            self,
            name=name,
            updated_at=edited_at,
            versions=(*self.versions, version),
        )

    @classmethod
    def from_dict(cls, medium_id: str, payload: Mapping[str, Any]) -> CultureMedium:
        """Decode a persisted medium."""
        raw_versions = payload.get("versions")
        if not isinstance(raw_versions, Sequence) or isinstance(
            raw_versions, (str, bytes)
        ):
            raise TcValidationError("A medium must carry a list of versions.")
        versions = tuple(MediumVersion.from_dict(entry) for entry in raw_versions)
        if not versions:
            raise TcValidationError("A medium must carry at least one version.")

        created_at = _required_text(payload.get("created_at"), "Created at", 64)
        return cls(
            id=medium_id,
            name=_required_text(payload.get("name"), "Name", MAX_NAME_LENGTH),
            created_at=created_at,
            updated_at=_optional_text(payload.get("updated_at"), "Updated at", 64)
            or created_at,
            versions=tuple(sorted(versions, key=lambda version: version.version)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the wire and storage representation.

        `current_version` is stated rather than left for the reader to derive:
        the card would otherwise have to trust the ordering of `versions` to
        know which one a new Plating pins.
        """
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "current_version": self.current_version.version,
            "versions": [version.to_dict() for version in self.versions],
        }
