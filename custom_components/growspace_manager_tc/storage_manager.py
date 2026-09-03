"""Storage manager for Growspace Manager TC."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION
from .data_access.culture_repository import CultureRepository


class StorageManager:
    """Move tissue-culture records between the repository and Home Assistant's store.

    The single owner of the `Store`: nothing else in the integration touches
    persistence, so the repository stays free of Home Assistant imports and can
    be exercised without a `hass`.
    """

    def __init__(
        self, hass: HomeAssistant, repository: CultureRepository | None = None
    ) -> None:
        """Initialize the storage manager."""
        self._store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
        self.repository = repository if repository is not None else CultureRepository()

    async def async_load(self) -> None:
        """Load persisted records into the repository."""
        self.repository.load(await self._store.async_load() or {})

    async def async_save(self) -> None:
        """Write the repository's records back to the store."""
        await self._store.async_save(self.repository.as_dict())
