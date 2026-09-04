"""The vocabulary every TC model shares: its errors and its value rules.

Two things live here rather than in each model.

The **errors** are three, and they are the ones the WebSocket layer maps onto
the codes the card already understands.  Every model raises a subclass rather
than a fresh hierarchy, so `websocket/_common.py` maps three base types once
instead of growing a row per collection — and a model that forgets to register
its error still reaches the card as the right code.

The **value rules** are the primitives every payload is validated with.  They
raise `TcValidationError` with a sentence naming the field, because that
message is shown to the grower: validation lives in the models, not in the
voluptuous schemas, so that a value someone typed and a wrong type from the
card do not arrive as the same error.
"""

from __future__ import annotations

from datetime import UTC, datetime
from math import isfinite
from typing import Any
from uuid import uuid4

__all__ = [
    "TcConflictError",
    "TcNotFoundError",
    "TcValidationError",
    "new_id",
    "number",
    "optional_text",
    "required_text",
    "utc_now_iso",
    "whole_number",
]


class TcValidationError(ValueError):
    """A payload the grower has to fix.

    Its message is shown to the user, so it names the field and says what is
    wrong with it.
    """


class TcConflictError(TcValidationError):
    """A value another record already answers to.

    A subclass because it is still the grower's form to fix, but a distinct
    type because the card is told `conflict` rather than `validation_failed` —
    the two lead to different UI.
    """


class TcNotFoundError(LookupError):
    """An identifier that is not in the collection it was looked up in."""


def utc_now_iso() -> str:
    """Return the current UTC instant as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()


def new_id() -> str:
    """Return an opaque identifier for a new record."""
    return uuid4().hex


def required_text(value: Any, field: str, limit: int) -> str:
    """Return `value` as trimmed non-empty text, or raise."""
    if not isinstance(value, str):
        raise TcValidationError(f"{field} must be text.")
    text = value.strip()
    if not text:
        raise TcValidationError(f"{field} is required.")
    if len(text) > limit:
        raise TcValidationError(f"{field} must be at most {limit} characters.")
    return text


def optional_text(value: Any, field: str, limit: int) -> str:
    """Return `value` as trimmed text, defaulting to empty, or raise."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise TcValidationError(f"{field} must be text.")
    text = value.strip()
    if len(text) > limit:
        raise TcValidationError(f"{field} must be at most {limit} characters.")
    return text


def number(value: Any, field: str, minimum: float, maximum: float) -> float:
    """Return `value` as a float inside its range, or raise.

    `bool` is rejected explicitly: it is an `int` to Python, and a checkbox
    reaching a concentration field is a bug worth naming rather than storing
    as 1.0.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TcValidationError(f"{field} must be a number.")
    as_float = float(value)
    if not isfinite(as_float):
        raise TcValidationError(f"{field} must be a number.")
    if not minimum <= as_float <= maximum:
        raise TcValidationError(f"{field} must be between {minimum:g} and {maximum:g}.")
    return as_float


def whole_number(value: Any, field: str, minimum: int, maximum: int) -> int:
    """Return `value` as an `int` inside its range, or raise.

    Separate from `number` because the fields that use it — an interval in
    days, a plantlet count — are counted rather than measured, and `30.5` days
    is a card bug rather than a precision the grower meant.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TcValidationError(f"{field} must be a whole number.")
    if not minimum <= value <= maximum:
        raise TcValidationError(f"{field} must be between {minimum} and {maximum}.")
    return int(value)
