"""The replate calendar — one entity per config entry, and what it refuses to be.

Every Culture awaiting a Replate is one all-day event on its Replate Due Date.
That is the whole entity, and the shape is chosen so automations can be written
against it: a grower's bench work is a day's work, not an appointment, and a
timed event would invent an hour nobody decided.

**Overdue is not a second definition here.** A vessel past its due date is
simply an event whose day has gone; the calendar keeps listing it, and the card
and any automation read "overdue" off the same date this entity draws.  V1
deliberately ships no overdue binary sensor for that reason — two definitions of
overdue is one more than the honesty budget allows (docs/v1-scope.md).

The events are computed from the repository on every read rather than cached,
and the entity re-renders when the store is written.  Nothing here holds a copy
of a due date: the interval it comes from lives on the Culture Line and can be
edited, so a cached one would be a number that used to be true.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import GrowspaceTcConfigEntry
from .const import DOMAIN, SIGNAL_TC_UPDATED
from .models.culture_line import Culture, CultureLine
from .storage_manager import StorageManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GrowspaceTcConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the replate calendar for a config entry."""
    async_add_entities([TcReplateCalendar(entry)])


class TcReplateCalendar(CalendarEntity):
    """Every Culture's next Replate, as one calendar.

    One entity per config entry rather than one per Culture Line: a grower with
    forty lines wants one calendar to subscribe to, and a per-line entity would
    make "what is due this week" a question about forty entities instead of a
    date range on one.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "replates"
    _attr_should_poll = False

    def __init__(self, entry: GrowspaceTcConfigEntry) -> None:
        """Initialize the calendar for one entry."""
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_replates"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Growspace Manager",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        """Re-render whenever the store is written.

        The signal is dispatched by the one place that saves, so a Maintenance
        Action, an Introduction and an edited interval all reach the calendar
        without any of their commands knowing it exists.
        """
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_TC_UPDATED, self._refresh)
        )

    @callback
    def _refresh(self) -> None:
        """Recompute the state from the repository."""
        self.async_write_ha_state()

    @property
    def _storage(self) -> StorageManager:
        storage: StorageManager = self._entry.runtime_data
        return storage

    def _events(self) -> list[CalendarEvent]:
        """Return one event per Culture awaiting a Replate, soonest first."""
        return [
            _event(line, culture, due)
            for line, culture, due in self._storage.repository.due_replates()
        ]

    @property
    def event(self) -> CalendarEvent | None:
        """Return the Replate that is most urgent.

        The earliest due date, which puts the longest-overdue vessel first and
        falls through to the next one due when nothing is late.  Home Assistant
        asks a calendar for "the current or next event"; for work that is late
        rather than scheduled, the oldest outstanding one is the honest answer
        to that question.
        """
        events = self._events()
        return events[0] if events else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return the Replates due in a window.

        Compared as local instants rather than as dates: an all-day event
        covers a whole local day, so a window that opens halfway through the
        day a vessel is due still overlaps it — and a date comparison would
        drop exactly the replate the grower asked about.
        """
        return [
            event
            for event in self._events()
            if event.start_datetime_local < end_date
            and event.end_datetime_local > start_date
        ]


def _event(line: CultureLine, culture: Culture, due: str) -> CalendarEvent:
    """Return the all-day event one Culture's Replate Due Date makes.

    Named from the Phenotype Reference's snapshot, because that is the only
    name this integration holds: phenotype identity is Growspace Manager's
    (ADR-0002) and nothing here resolves an ID.  A calendar the grower reads on
    their phone showing the name the line was started under is a far better
    failure than one showing an opaque key.
    """
    day = dt_util.as_local(datetime.fromisoformat(due)).date()
    where = culture.location or "—"
    return CalendarEvent(
        start=day,
        end=day + timedelta(days=1),
        summary=f"Replate {line.phenotype.name_snapshot}",
        description=(
            f"Stage: {culture.stage.value}\n"
            f"Location: {where}\n"
            f"Last replated: {culture.last_replated_at}"
        ),
        location=culture.location or None,
        uid=culture.id,
    )
