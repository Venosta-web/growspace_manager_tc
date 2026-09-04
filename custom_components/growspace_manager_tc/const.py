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
