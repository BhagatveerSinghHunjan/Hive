"""Google Calendar integration tests (agenda, conflicts, free slots, writes)."""

import asyncio

from hive.integrations import calendar as calendar_module
from hive.permissions import get_tool_tier, should_auto_allow
from hive.tools import TOOLS


class _FakeRequest:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        return self._payload


class _FakeEvents:
    def __init__(self, items=None, existing=None):
        self._items = items or []
        self._existing = existing or {}
        self.last_insert = None
        self.last_update = None
        self.deleted = None

    def list(self, **kwargs):
        self.last_list = kwargs
        return _FakeRequest({"items": self._items})

    def get(self, calendarId, eventId):
        return _FakeRequest({**self._existing, "id": eventId})

    def insert(self, **kwargs):
        self.last_insert = kwargs
        body = kwargs["body"]
        return _FakeRequest({
            **body,
            "id": "ev1",
            "htmlLink": "https://calendar.google.com/event?eid=ev1",
            "status": "confirmed",
        })

    def update(self, **kwargs):
        self.last_update = kwargs
        return _FakeRequest({**kwargs["body"], "id": kwargs["eventId"]})

    def delete(self, **kwargs):
        self.deleted = kwargs
        return _FakeRequest({})


class _FakeService:
    def __init__(self, events):
        self._events = events

    def events(self):
        return self._events


def _install(monkeypatch, events):
    service = _FakeService(events)
    monkeypatch.setattr(
        calendar_module.google_auth,
        "get_service",
        lambda api, version: service,
    )
    return events


def _timed_event(event_id="e1", start="2026-12-01T09:00:00+05:30",
                 end="2026-12-01T10:00:00+05:30", summary="Venue walkthrough"):
    return {
        "id": event_id,
        "summary": summary,
        "status": "confirmed",
        "start": {"dateTime": start},
        "end": {"dateTime": end},
        "location": "Auditorium",
        "attendees": [{"email": "venue@example.com", "responseStatus": "accepted"}],
    }


def test_calendar_tools_registered_with_tiers():
    expected = {
        "calendar_list_events": "safe",
        "calendar_find_free_slots": "safe",
        "calendar_detect_conflicts": "safe",
        "calendar_create_event": "sensitive",
        "calendar_update_event": "sensitive",
        "calendar_delete_event": "dangerous",
    }
    for name, tier in expected.items():
        assert name in TOOLS
        assert get_tool_tier(name) == tier


def test_calendar_writes_require_approval():
    assert should_auto_allow("calendar_create_event", "") is False
    assert should_auto_allow("calendar_update_event", "") is False
    assert should_auto_allow("calendar_delete_event", "") is False


def test_list_events_shapes_summaries(monkeypatch):
    _install(monkeypatch, _FakeEvents([_timed_event()]))
    result = calendar_module.list_events(
        time_min="2026-12-01T00:00:00",
        time_max="2026-12-02T00:00:00",
    )
    assert result["count"] == 1
    event = result["events"][0]
    assert event["event_id"] == "e1"
    assert event["summary"] == "Venue walkthrough"
    assert event["attendees"][0]["email"] == "venue@example.com"
    assert result["timezone"]


def test_detect_conflicts_overlapping_event(monkeypatch):
    _install(monkeypatch, _FakeEvents([_timed_event()]))
    result = calendar_module.detect_conflicts(
        "2026-12-01T09:30:00", "2026-12-01T10:30:00"
    )
    assert result["count"] == 1
    assert result["available"] is False

    free = calendar_module.detect_conflicts(
        "2026-12-01T11:00:00", "2026-12-01T12:00:00"
    )
    assert free["count"] == 0
    assert free["available"] is True


def test_find_free_slots_skips_busy_time(monkeypatch):
    _install(monkeypatch, _FakeEvents([_timed_event()]))
    result = calendar_module.find_free_slots(
        duration_minutes=60,
        range_start="2026-12-01T09:00:00",
        range_end="2026-12-01T13:00:00",
        max_slots=3,
    )
    assert result["count"] >= 1
    assert "10:00" in result["slots"][0]["start"]


def test_create_event_passes_attendees_and_timezone(monkeypatch):
    events = _install(monkeypatch, _FakeEvents())
    result = calendar_module.create_event(
        "Venue confirmed",
        "2026-12-04T15:00:00",
        "2026-12-04T16:00:00",
        location="Auditorium",
        attendees="venue@example.com,advisor@example.com",
    )
    assert result["status"] == "event_created"
    assert result["invites_sent"] is True
    body = events.last_insert["body"]
    assert body["summary"] == "Venue confirmed"
    assert len(body["attendees"]) == 2
    assert body["start"]["timeZone"] == calendar_module.HIVE_TIMEZONE
    assert events.last_insert["sendUpdates"] == "all"


def test_update_and_delete_event(monkeypatch):
    events = _install(monkeypatch, _FakeEvents(
        existing=_timed_event(),
    ))
    updated = calendar_module.update_event(
        "e1", summary="Venue confirmed", location="Main hall"
    )
    assert updated["status"] == "event_updated"
    assert events.last_update["eventId"] == "e1"

    deleted = calendar_module.delete_event("e1")
    assert deleted["status"] == "event_deleted"
    assert events.deleted["eventId"] == "e1"


def test_calendar_tool_dispatch_through_registry(monkeypatch):
    from hive.integrations.registry import run_integration_tool

    _install(monkeypatch, _FakeEvents([_timed_event()]))
    result = asyncio.run(
        run_integration_tool(
            "calendar_list_events",
            time_min="2026-12-01T00:00:00",
            time_max="2026-12-02T00:00:00",
        )
    )
    assert result["count"] == 1
