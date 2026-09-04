"""Tests for the replate calendar."""

from datetime import datetime, timedelta
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.growspace_manager_tc.const import DOMAIN
from custom_components.growspace_manager_tc.models.culture_line import (
    PhenotypeReference,
    ReplateIntervals,
)
from custom_components.growspace_manager_tc.storage_manager import StorageManager
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

INTERVALS: dict[str, Any] = {"multiplication": 30, "rooting": 21}
CALENDAR = "calendar.mock_title_replates"


@pytest.fixture
async def entry(hass: HomeAssistant, growspace_manager_loaded: None) -> MockConfigEntry:
    """Return a loaded config entry."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _introduce(entry: MockConfigEntry, name: str, *, days_ago: int, **kwargs: Any):
    """Introduce a line whose vessel was last replated `days_ago` days ago."""
    storage: StorageManager = entry.runtime_data
    when = (dt_util.utcnow() - timedelta(days=days_ago)).isoformat()
    return storage.repository.introduce_culture_line(
        PhenotypeReference.taken(f"{name}|1", name, now=when),
        ReplateIntervals.from_payload(INTERVALS),
        now=when,
        **kwargs,
    )


async def test_the_entry_gets_one_calendar(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """One calendar to subscribe to, not one per line."""
    state = hass.states.get(CALENDAR)

    assert state is not None
    assert state.state == "off"


async def test_a_culture_becomes_an_all_day_event_on_its_due_date(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Bench work is a day's work, so the event is all-day rather than timed."""
    line, culture = _introduce(entry, "Blue Dream", days_ago=1, location="Shelf A")
    storage: StorageManager = entry.runtime_data
    await storage.async_save()
    await hass.async_block_till_done()

    calendar = hass.data["calendar"].get_entity(CALENDAR)
    event = calendar.event

    assert event is not None
    assert event.all_day
    assert event.uid == culture.id
    assert line.phenotype.name_snapshot in event.summary
    assert event.location == "Shelf A"
    assert event.end == event.start + timedelta(days=1)


async def test_the_most_urgent_replate_is_the_one_reported(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """The longest-overdue vessel first: late work is what a grower needs told."""
    _late_line, late = _introduce(entry, "Aaa late", days_ago=40)
    _introduce(entry, "Zzz soon", days_ago=2)
    storage: StorageManager = entry.runtime_data
    await storage.async_save()
    await hass.async_block_till_done()

    calendar = hass.data["calendar"].get_entity(CALENDAR)

    assert calendar.event is not None
    assert calendar.event.uid == late.id
    assert calendar.event.start < dt_util.now().date()


async def test_events_are_returned_for_a_window(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """A range query answers with the replates that fall inside it."""
    _introduce(entry, "Due soon", days_ago=29)
    _introduce(entry, "Due much later", days_ago=0)
    storage: StorageManager = entry.runtime_data
    await storage.async_save()
    await hass.async_block_till_done()

    calendar = hass.data["calendar"].get_entity(CALENDAR)
    start = dt_util.now()
    events = await calendar.async_get_events(hass, start, start + timedelta(days=7))

    assert [event.summary for event in events] == ["Replate Due soon"]


async def test_an_ended_or_archived_vessel_leaves_the_calendar(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """A line put away is not work, and a discarded vessel is not late."""
    storage: StorageManager = entry.runtime_data
    archived_line, _archived = _introduce(entry, "Archived", days_ago=40)
    _kept_line, discarded = _introduce(entry, "Discarded", days_ago=40)
    await storage.async_save()
    await hass.async_block_till_done()

    calendar = hass.data["calendar"].get_entity(CALENDAR)
    assert calendar.event is not None

    storage.repository.set_culture_line_archived(archived_line.id, True)
    storage.repository.discard_culture(discarded.id, "spent")
    await storage.async_save()
    await hass.async_block_till_done()

    assert calendar.event is None
    assert hass.states.get(CALENDAR).state == "off"


async def test_the_calendar_re_renders_when_the_store_is_written(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """One signal from the one place that saves, so no command has to know."""
    calendar = hass.data["calendar"].get_entity(CALENDAR)
    assert calendar.event is None

    # Due today, so the entity is not merely holding an event but reporting it:
    # a calendar's state is "on" while an event is running, and an overdue
    # replate's day has already gone.
    _introduce(entry, "Blue Dream", days_ago=30)
    storage: StorageManager = entry.runtime_data
    await storage.async_save()
    await hass.async_block_till_done()

    assert hass.states.get(CALENDAR).state == "on"


async def test_an_unreadable_anchor_is_left_off_rather_than_guessed(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """A due date invented from a stamp nothing can read would be shown as fact."""
    storage: StorageManager = entry.runtime_data
    _line, culture = _introduce(entry, "Blue Dream", days_ago=1)
    storage.repository._cultures.records[culture.id] = type(culture).from_dict(
        culture.id, {**culture.to_dict(), "last_replated_at": "whenever"}
    )
    await storage.async_save()
    await hass.async_block_till_done()

    calendar = hass.data["calendar"].get_entity(CALENDAR)

    assert calendar.event is None


async def test_the_window_is_read_in_local_time(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """The due date is a day, and which day depends on the grower's timezone."""
    _introduce(entry, "Blue Dream", days_ago=30)
    storage: StorageManager = entry.runtime_data
    await storage.async_save()
    await hass.async_block_till_done()

    calendar = hass.data["calendar"].get_entity(CALENDAR)
    far_past = datetime(2020, 1, 1, tzinfo=dt_util.UTC)
    events = await calendar.async_get_events(hass, far_past, dt_util.utcnow())

    assert len(events) == 1
    assert events[0].start <= dt_util.now().date()
