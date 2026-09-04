"""Constants for the Growspace Manager TC integration."""

from typing import Final

DOMAIN: Final = "growspace_manager_tc"

# The integration this one companions. Growspace Manager owns phenotype
# identity; TC only references it, and refuses to run without it loaded.
GROWSPACE_MANAGER_DOMAIN: Final = "growspace_manager"

DEFAULT_NAME: Final = "Growspace Manager TC"

STORAGE_KEY: Final = f"{DOMAIN}.cultures"
STORAGE_VERSION: Final = 1

# The version of the TC WebSocket contract this integration speaks. The card
# capability-detects TC by calling `growspace_manager_tc/get_manifest`; this
# number tells it which shape of the namespace answered, independently of the
# integration's own release version.
TC_CONTRACT_VERSION: Final = 1

# Sent when the namespace is registered but no entry is loaded. Home Assistant
# never unregisters a WebSocket command, so a removed or unloaded integration
# still answers — with this.
WS_ERR_NOT_LOADED: Final = "not_loaded"

# Error codes the card already understands, mirroring growspace_manager's
# vocabulary (`services/utils.py`). `hass-call.ts` narrows any code outside that
# set to `internal_error`, so a TC-only spelling would cost the card the ability
# to tell a rejected form from a broken backend.
WS_ERR_VALIDATION_FAILED: Final = "validation_failed"
WS_ERR_NOT_FOUND: Final = "entity_not_found"
WS_ERR_CONFLICT: Final = "conflict"

# The persisted collection of Culture Media. "Media" unqualified is reserved in
# Growspace Manager for substrate (see CONTEXT.md), so the key is spelled out
# here and on the wire.
COLLECTION_CULTURE_MEDIA: Final = "culture_media"

# The persisted collections of Culture Lines and their Cultures. Cultures are
# their own collection rather than a list inside their line, so a Maintenance
# Action can write one vessel without rewriting the lineage it belongs to.
COLLECTION_CULTURE_LINES: Final = "culture_lines"
COLLECTION_CULTURES: Final = "cultures"

# The manifest feature the card gates its medium library on. A release that
# serves these commands names it; an older release installed under a newer card
# does not, and the card renders no library rather than a broken one.
FEATURE_CULTURE_MEDIA: Final = "culture_media"

# The manifest feature the card gates the culture board and the Introduction
# form on, on the same terms.
FEATURE_CULTURE_LINES: Final = "culture_lines"
