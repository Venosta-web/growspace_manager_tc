"""Tests for the storage manager and the culture repository."""

from typing import Any

from custom_components.growspace_manager_tc.const import STORAGE_KEY, STORAGE_VERSION
from custom_components.growspace_manager_tc.data_access.culture_repository import (
    CultureRepository,
)
from custom_components.growspace_manager_tc.storage_manager import StorageManager
from homeassistant.core import HomeAssistant


def test_repository_starts_empty() -> None:
    """A fresh repository persists nothing."""
    assert CultureRepository().as_dict() == {}


def test_repository_round_trips_records() -> None:
    """Records a newer version wrote survive a load/save cycle."""
    repository = CultureRepository()
    repository.load({"culture_lines": {"line-1": {"name": "Blue Dream"}}})

    assert repository.as_dict() == {"culture_lines": {"line-1": {"name": "Blue Dream"}}}


def test_repository_does_not_alias_the_payload() -> None:
    """Loaded and returned payloads are copies, not the caller's dict."""
    payload: dict[str, Any] = {"culture_lines": {}}
    repository = CultureRepository()
    repository.load(payload)

    payload["culture_lines"] = {"line-1": {}}
    assert repository.as_dict() == {"culture_lines": {}}

    repository.as_dict()["culture_lines"] = {"line-2": {}}
    assert repository.as_dict() == {"culture_lines": {}}


async def test_load_of_an_empty_store(hass: HomeAssistant) -> None:
    """A first run finds no store and starts with an empty repository."""
    storage = StorageManager(hass)

    await storage.async_load()

    assert storage.repository.as_dict() == {}


async def test_save_writes_the_repository(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Saving writes the repository's records under the versioned key."""
    repository = CultureRepository()
    repository.load({"culture_lines": {"line-1": {"name": "Blue Dream"}}})
    storage = StorageManager(hass, repository)

    await storage.async_save()

    assert hass_storage[STORAGE_KEY]["version"] == STORAGE_VERSION
    assert hass_storage[STORAGE_KEY]["data"] == {
        "culture_lines": {"line-1": {"name": "Blue Dream"}}
    }
