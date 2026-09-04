"""WebSocket API package for the Growspace Manager TC integration.

Every command lives under the `growspace_manager_tc/` namespace, so nothing
here can collide with the commands Growspace Manager registers.
"""

from __future__ import annotations

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .manifest import (
    MANIFEST_FEATURES,
    SCHEMA_WS_GET_MANIFEST,
    WS_TYPE_GET_MANIFEST,
    async_build_manifest,
    websocket_get_manifest,
)

__all__ = [
    "MANIFEST_FEATURES",
    "SCHEMA_WS_GET_MANIFEST",
    "WS_TYPE_GET_MANIFEST",
    "async_build_manifest",
    "async_register_commands",
    "websocket_get_manifest",
]


@callback
def async_register_commands(hass: HomeAssistant) -> None:
    """Register the TC namespace.

    Called from `async_setup_entry`, and therefore only once Home Assistant has
    an entry to load — before that the namespace does not exist at all, which is
    exactly the signal the card reads. Registration is idempotent: a reload
    re-registers the same handler over itself.
    """
    websocket_api.async_register_command(
        hass,
        WS_TYPE_GET_MANIFEST,
        websocket_get_manifest,
        SCHEMA_WS_GET_MANIFEST,
    )
