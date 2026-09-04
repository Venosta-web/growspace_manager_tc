"""Tests for setting up, reloading and unloading the config entry."""

from typing import Any

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.growspace_manager_tc.const import (
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from custom_components.growspace_manager_tc.storage_manager import StorageManager
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_retries_without_growspace_manager(hass: HomeAssistant) -> None:
    """An entry that outlived Growspace Manager retries instead of failing."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_and_reload(
    hass: HomeAssistant, growspace_manager_loaded: None
) -> None:
    """Setup exposes a storage manager, and reload rebuilds it."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    first = entry.runtime_data
    assert isinstance(first, StorageManager)

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert isinstance(entry.runtime_data, StorageManager)
    assert entry.runtime_data is not first


async def test_unload(hass: HomeAssistant, growspace_manager_loaded: None) -> None:
    """Unloading leaves the entry not loaded and removable."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_loads_persisted_records(
    hass: HomeAssistant,
    growspace_manager_loaded: None,
    hass_storage: dict[str, Any],
) -> None:
    """Whatever the store already holds is in the repository after setup."""
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "data": {"platings": {"plating-1": {"medium_version": 2}}},
    }
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    storage: StorageManager = entry.runtime_data
    assert storage.repository.as_dict() == {
        "culture_media": {},
        "culture_lines": {},
        "cultures": {},
        "platings": {"plating-1": {"medium_version": 2}},
    }
