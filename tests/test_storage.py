"""Tests for the storage manager and the culture repository."""

from typing import Any

from custom_components.growspace_manager_tc.const import STORAGE_KEY, STORAGE_VERSION
from custom_components.growspace_manager_tc.data_access.culture_repository import (
    CultureRepository,
)
from custom_components.growspace_manager_tc.storage_manager import StorageManager
from homeassistant.core import HomeAssistant

# Every collection this version owns, written even when it holds nothing: the
# manifest counts whatever `as_dict` reports, and a key that only appeared once
# a record existed would leave the card unable to tell a version that has the
# collection from one that has never heard of it.
EMPTY: dict[str, Any] = {
    "culture_media": {},
    "culture_lines": {},
    "cultures": {},
    "maintenance_actions": {},
    "pairings": {},
}


def test_repository_starts_empty() -> None:
    """A fresh repository persists the collections it owns, holding nothing."""
    assert CultureRepository().as_dict() == EMPTY


def test_repository_round_trips_records() -> None:
    """Records a newer version wrote survive a load/save cycle."""
    repository = CultureRepository()
    repository.load({"platings": {"plating-1": {"medium_version": 2}}})

    assert repository.as_dict() == {
        **EMPTY,
        "platings": {"plating-1": {"medium_version": 2}},
    }


def test_repository_does_not_alias_the_payload() -> None:
    """Loaded and returned payloads are copies, not the caller's dict."""
    payload: dict[str, Any] = {"platings": {}}
    repository = CultureRepository()
    repository.load(payload)

    payload["platings"] = {"plating-1": {}}
    assert repository.as_dict()["platings"] == {}

    repository.as_dict()["platings"] = {"plating-2": {}}
    assert repository.as_dict()["platings"] == {}


async def test_load_of_an_empty_store(hass: HomeAssistant) -> None:
    """A first run finds no store and starts with an empty repository."""
    storage = StorageManager(hass)

    await storage.async_load()

    assert storage.repository.as_dict() == EMPTY


async def test_save_writes_the_repository(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Saving writes the repository's records under the versioned key."""
    repository = CultureRepository()
    repository.load({"platings": {"plating-1": {"medium_version": 2}}})
    storage = StorageManager(hass, repository)

    await storage.async_save()

    assert hass_storage[STORAGE_KEY]["version"] == STORAGE_VERSION
    assert hass_storage[STORAGE_KEY]["data"] == {
        **EMPTY,
        "platings": {"plating-1": {"medium_version": 2}},
    }
