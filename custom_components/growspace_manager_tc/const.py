"""Constants for the Growspace Manager TC integration."""

from typing import Final

DOMAIN: Final = "growspace_manager_tc"

# The integration this one companions. Growspace Manager owns phenotype
# identity; TC only references it, and refuses to run without it loaded.
GROWSPACE_MANAGER_DOMAIN: Final = "growspace_manager"

DEFAULT_NAME: Final = "Growspace Manager TC"

STORAGE_KEY: Final = f"{DOMAIN}.cultures"
STORAGE_VERSION: Final = 1
