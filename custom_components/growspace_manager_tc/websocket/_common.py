"""Shared plumbing for the TC WebSocket namespace.

Two things every command in the namespace has to do, and neither is worth
repeating per handler: find the loaded entry's storage, and turn a domain error
into an error code the card already understands.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
import logging
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from ..const import (
    DOMAIN,
    WS_ERR_CONFLICT,
    WS_ERR_NOT_FOUND,
    WS_ERR_NOT_LOADED,
    WS_ERR_VALIDATION_FAILED,
)
from ..models.common import TcConflictError, TcNotFoundError, TcValidationError
from ..storage_manager import StorageManager

_LOGGER = logging.getLogger(__name__)

# Ordered most specific first: `TcConflictError` is a `TcValidationError`, and
# the card renders the two differently.  Three base types rather than a row per
# collection: a model that raises the shared error reaches the card as the right
# code without this table having to learn it exists.
_ERROR_CODES: tuple[tuple[type[Exception], str], ...] = (
    (TcConflictError, WS_ERR_CONFLICT),
    (TcNotFoundError, WS_ERR_NOT_FOUND),
    (TcValidationError, WS_ERR_VALIDATION_FAILED),
)

TcPayloadHandler = Callable[
    [HomeAssistant, StorageManager, dict[str, Any]], Awaitable[Any]
]
# `websocket_api.async_response` hands back a synchronous handler that
# schedules the coroutine, which is what `async_register_command` expects.
TcWsHandler = Callable[
    [HomeAssistant, websocket_api.ActiveConnection, dict[str, Any]], None
]


def loaded_storage(hass: HomeAssistant) -> StorageManager | None:
    """Return the storage of the loaded entry, or None if there is none.

    Home Assistant offers no way to unregister a WebSocket command, so the
    namespace outlives the entry that registered it. Answering from
    `runtime_data` of a loaded entry is what keeps a removed integration
    indistinguishable — to the card — from one that was never installed.
    """
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            storage: StorageManager = entry.runtime_data
            return storage
    return None


def tc_command(handler: TcPayloadHandler) -> TcWsHandler:
    """Turn a payload-returning handler into a registered WebSocket command.

    The handler receives the loaded storage and returns the result payload; it
    raises for everything else. Nothing in the namespace touches the connection
    directly, so no command can forget to refuse when the entry is gone, and no
    two commands can spell the same rejection differently.
    """

    @websocket_api.async_response
    @wraps(handler)
    async def wrapper(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        storage = loaded_storage(hass)
        if storage is None:
            connection.send_error(
                msg["id"],
                WS_ERR_NOT_LOADED,
                "Growspace Manager TC is installed but has no loaded config entry.",
            )
            return

        try:
            payload = await handler(hass, storage, msg)
        except Exception as err:
            for error_type, code in _ERROR_CODES:
                if isinstance(err, error_type):
                    connection.send_error(msg["id"], code, str(err))
                    return
            _LOGGER.exception("Unhandled error in %s", msg.get("type"))
            connection.send_error(
                msg["id"], websocket_api.const.ERR_UNKNOWN_ERROR, str(err)
            )
            return

        connection.send_result(msg["id"], payload)

    return wrapper
