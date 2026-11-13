"""Google Calendar tools: read agenda, find free slots, detect conflicts,
create/update events.

Credential handling lives in :mod:`hive.integrations.google_auth`; this module
only receives API services and returns credential-safe event summaries.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from hive.config import GOOGLE_CALENDAR_ID, HIVE_TIMEZONE
from hive.integrations.google_auth import google_auth

try:
    from googleapiclient.errors import HttpError
except Exception:  # pragma: no cover - optional dependency
    HttpError = None

logger = logging.getLogger(__name__)

MAX_EVENTS = 100
DEFAULT_DAYS = 7
DEFAULT_DURATION = 30
DEFAULT_WORKING_START = 9
DEFAULT_WORKING_END = 18


class CalendarError(RuntimeError):
    """Raised when a calendar operation cannot be completed."""


def _api_error(exc: Exception) -> dict:
    status = getattr(getattr(exc, "resp", None), "status", None)
    message = str(exc)
    return {
        "error": message[:400],
        "status_code": status,
        "needs_auth": status in (401, 403),
        "setup_hint": (
            "Reconnect Google and allow the Calendar scope: "
            "python -m hive.cli --connect-google"
        ) if status in (401, 403) else None,
    }


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(HIVE_TIMEZONE)
    except Exception:
        return ZoneInfo("UTC")


def _now() -> datetime:
    return datetime.now(_tz())


def _parse_dt(value: str | datetime | None, *, default: datetime | None = None) -> datetime | None:
    if value is None:
        return default
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return default
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
                try:
                    dt = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    continue
            else:
                raise CalendarError(f"Could not parse date/time: {value!r}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_tz())
    return dt.astimezone(_tz())


def _dt_to_rfc3339(dt: datetime) -> str:
    return dt.astimezone(_tz()).isoformat()


def _event_time(container: dict, key: str) -> str | None:
    part = container.get(key) or {}
    return part.get("dateTime") or part.get("date")


def _event_summary(event: dict) -> dict:
    attendees = [
        {
            "email": a.get("email"),
            "name": a.get("displayName"),
            "status": a.get("responseStatus"),
            "organizer": bool(a.get("organizer")),
        }
        for a in event.get("attendees", []) or []
    ]
    return {
        "event_id": event.get("id"),
        "summary": event.get("summary") or "(no title)",
        "start": _event_time(event, "start"),
        "end": _event_time(event, "end"),
        "location": event.get("location") or "",
        "description": (event.get("description") or "")[:400],
        "attendees": attendees,
        "status": event.get("status"),
        "organizer": (event.get("organizer") or {}).get("email"),
        "html_link": event.get("htmlLink"),
        "meet_link": event.get("hangoutLink"),
    }


def _list_events_raw(
    time_min: datetime,
    time_max: datetime,
    calendar_id: str = GOOGLE_CALENDAR_ID,
    max_results: int = MAX_EVENTS,
    query: str | None = None,
) -> list[dict]:
    service = google_auth.get_service("calendar", "v3")
    params: dict[str, Any] = {
        "calendarId": calendar_id or GOOGLE_CALENDAR_ID,
        "timeMin": _dt_to_rfc3339(time_min),
        "timeMax": _dt_to_rfc3339(time_max),
        "singleEvents": True,
        "orderBy": "startTime",
        "maxResults": max(1, min(int(max_results or MAX_EVENTS), MAX_EVENTS)),
    }
    if query:
        params["q"] = query
    result = service.events().list(**params).execute()
    return result.get("items", []) or []


def list_events(
    time_min: str | None = None,
    time_max: str | None = None,
    days: int = DEFAULT_DAYS,
    calendar_id: str = GOOGLE_CALENDAR_ID,
    max_results: int = 50,
    query: str | None = None,
) -> dict:
    """List upcoming events in a time window."""
    start = _parse_dt(time_min, default=_now().replace(minute=0, second=0, microsecond=0))
    end = _parse_dt(time_max, default=start + timedelta(days=max(1, int(days or DEFAULT_DAYS))))
    if end <= start:
        return {"error": "time_max must be after time_min"}

    try:
        events = _list_events_raw(start, end, calendar_id, max_results, query)
    except Exception as exc:
        if HttpError is not None and isinstance(exc, HttpError):
            return _api_error(exc)
        raise

    summaries = [_event_summary(e) for e in events if e.get("status") != "cancelled"]
    return {
        "calendar_id": calendar_id or GOOGLE_CALENDAR_ID,
        "time_min": _dt_to_rfc3339(start),
        "time_max": _dt_to_rfc3339(end),
        "timezone": HIVE_TIMEZONE,
        "count": len(summaries),
        "events": summaries,
    }


def _to_interval(event: dict) -> tuple[datetime, datetime] | None:
    start_raw = _event_time(event, "start")
    end_raw = _event_time(event, "end")
    if not start_raw:
        return None
    if len(start_raw) == 10 and "dateTime" not in (event.get("start") or {}):
        day = date.fromisoformat(start_raw)
        start = datetime.combine(day, time(0, 0), tzinfo=_tz())
        end = start + timedelta(days=1)
        return start, end
    start = _parse_dt(start_raw)
    end = _parse_dt(end_raw) if end_raw else start + timedelta(hours=1)
    return start, end


def detect_conflicts(
    start: str,
    end: str,
    calendar_id: str = GOOGLE_CALENDAR_ID,
) -> dict:
    """Return events overlapping the requested window."""
    start_dt = _parse_dt(start)
    end_dt = _parse_dt(end)
    if end_dt <= start_dt:
        return {"error": "end must be after start"}

    try:
        events = _list_events_raw(start_dt, end_dt, calendar_id)
    except Exception as exc:
        if HttpError is not None and isinstance(exc, HttpError):
            return _api_error(exc)
        raise

    conflicts = []
    for event in events:
        interval = _to_interval(event)
        if not interval:
            continue
        ev_start, ev_end = interval
        if ev_start < end_dt and ev_end > start_dt:
            conflicts.append(_event_summary(event))

    return {
        "start": _dt_to_rfc3339(start_dt),
        "end": _dt_to_rfc3339(end_dt),
        "count": len(conflicts),
        "conflicts": conflicts,
        "available": len(conflicts) == 0,
    }


def find_free_slots(
    duration_minutes: int = DEFAULT_DURATION,
    range_start: str | None = None,
    range_end: str | None = None,
    days: int = DEFAULT_DAYS,
    working_start: int = DEFAULT_WORKING_START,
    working_end: int = DEFAULT_WORKING_END,
    max_slots: int = 5,
    include_weekends: bool = False,
    calendar_id: str = GOOGLE_CALENDAR_ID,
) -> dict:
    """Find open working-hour slots that fit ``duration_minutes``."""
    try:
        duration = max(15, int(duration_minutes or DEFAULT_DURATION))
    except (TypeError, ValueError):
        duration = DEFAULT_DURATION
    start = _parse_dt(range_start, default=_now())
    end = _parse_dt(range_end, default=start + timedelta(days=max(1, int(days or DEFAULT_DAYS))))
    if end <= start:
        return {"error": "range_end must be after range_start"}

    try:
        events = _list_events_raw(start, end, calendar_id, MAX_EVENTS)
    except Exception as exc:
        if HttpError is not None and isinstance(exc, HttpError):
            return _api_error(exc)
        raise

    busy: list[tuple[datetime, datetime]] = []
    for event in events:
        if event.get("transparency") == "transparent":
            continue
        interval = _to_interval(event)
        if interval:
            busy.append(interval)

    slots: list[dict] = []
    cursor_day = start.date()
    last_day = end.date()
    work_start_hour = max(0, min(23, int(working_start)))
    work_end_hour = max(work_start_hour + 1, min(24, int(working_end)))

    while cursor_day <= last_day and len(slots) < max(1, int(max_slots)):
        if not include_weekends and cursor_day.weekday() >= 5:
            cursor_day += timedelta(days=1)
            continue

        day_start = datetime.combine(cursor_day, time(work_start_hour, 0), tzinfo=_tz())
        day_end = datetime.combine(cursor_day, time(work_end_hour, 0), tzinfo=_tz())
        candidate = max(day_start, start)

        while candidate + timedelta(minutes=duration) <= min(day_end, end):
            slot_end = candidate + timedelta(minutes=duration)
            if all(slot_end <= b_start or candidate >= b_end for b_start, b_end in busy):
                slots.append({
                    "start": _dt_to_rfc3339(candidate),
                    "end": _dt_to_rfc3339(slot_end),
                    "display": candidate.strftime("%a %d %b, %I:%M %p").replace(" 0", " "),
                })
                if len(slots) >= max(1, int(max_slots)):
                    break
            candidate += timedelta(minutes=30)

        cursor_day += timedelta(days=1)

    return {
        "duration_minutes": duration,
        "timezone": HIVE_TIMEZONE,
        "count": len(slots),
        "slots": slots,
    }


def _normalize_attendees(attendees: Iterable[str] | str | None) -> list[dict]:
    if not attendees:
        return []
    if isinstance(attendees, str):
        addresses = [a.strip() for a in attendees.split(",") if a.strip()]
    else:
        addresses = [str(a).strip() for a in attendees if str(a).strip()]
    return [{"email": email} for email in addresses]


def create_event(
    summary: str,
    start: str,
    end: str,
    description: str | None = None,
    location: str | None = None,
    attendees: Iterable[str] | str | None = None,
    calendar_id: str = GOOGLE_CALENDAR_ID,
    reminders_minutes: int | str | None = None,
    add_google_meet: bool = False,
) -> dict:
    """Create a calendar event. Sensitive — always behind human approval."""
    summary = (summary or "").strip()
    if not summary:
        return {"error": "summary is required"}

    start_dt = _parse_dt(start)
    end_dt = _parse_dt(end)
    if end_dt <= start_dt:
        return {"error": "end must be after start"}

    body: dict[str, Any] = {
        "summary": summary[:300],
        "start": {"dateTime": _dt_to_rfc3339(start_dt), "timeZone": HIVE_TIMEZONE},
        "end": {"dateTime": _dt_to_rfc3339(end_dt), "timeZone": HIVE_TIMEZONE},
    }
    if description:
        body["description"] = str(description)[:8000]
    if location:
        body["location"] = str(location)[:500]
    attendee_list = _normalize_attendees(attendees)
    if attendee_list:
        body["attendees"] = attendee_list
    if reminders_minutes not in (None, ""):
        try:
            minutes = max(0, int(reminders_minutes))
            body["reminders"] = {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": minutes}],
            }
        except (TypeError, ValueError):
            pass

    params: dict[str, Any] = {
        "calendarId": calendar_id or GOOGLE_CALENDAR_ID,
        "body": body,
        "sendUpdates": "all" if attendee_list else "none",
    }
    if add_google_meet:
        params["conferenceDataVersion"] = 1
        body["conferenceData"] = {
            "createRequest": {
                "requestId": f"hive-{int(datetime.now().timestamp() * 1000)}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }

    service = google_auth.get_service("calendar", "v3")
    try:
        created = service.events().insert(**params).execute()
    except Exception as exc:
        if HttpError is not None and isinstance(exc, HttpError):
            return _api_error(exc)
        raise

    return {
        "status": "event_created",
        "event": _event_summary(created),
        "invites_sent": bool(attendee_list),
    }


def update_event(
    event_id: str,
    summary: str | None = None,
    start: str | None = None,
    end: str | None = None,
    description: str | None = None,
    location: str | None = None,
    attendees: Iterable[str] | str | None = None,
    calendar_id: str = GOOGLE_CALENDAR_ID,
) -> dict:
    """Update an existing event. Sensitive — always behind human approval."""
    event_id = (event_id or "").strip()
    if not event_id:
        return {"error": "event_id is required"}

    service = google_auth.get_service("calendar", "v3")
    cal = calendar_id or GOOGLE_CALENDAR_ID
    try:
        existing = service.events().get(calendarId=cal, eventId=event_id).execute()
    except Exception as exc:
        if HttpError is not None and isinstance(exc, HttpError):
            return _api_error(exc)
        raise

    body: dict[str, Any] = {}
    if summary is not None:
        body["summary"] = str(summary)[:300]
    if description is not None:
        body["description"] = str(description)[:8000]
    if location is not None:
        body["location"] = str(location)[:500]
    if start is not None:
        body["start"] = {"dateTime": _dt_to_rfc3339(_parse_dt(start)), "timeZone": HIVE_TIMEZONE}
    if end is not None:
        body["end"] = {"dateTime": _dt_to_rfc3339(_parse_dt(end)), "timeZone": HIVE_TIMEZONE}
    if attendees is not None:
        body["attendees"] = _normalize_attendees(attendees)
    if not body:
        return {"error": "nothing to update"}

    updated_body = {**existing, **body}
    try:
        updated = (
            service.events()
            .update(calendarId=cal, eventId=event_id, body=updated_body, sendUpdates="all")
            .execute()
        )
    except Exception as exc:
        if HttpError is not None and isinstance(exc, HttpError):
            return _api_error(exc)
        raise

    return {"status": "event_updated", "event": _event_summary(updated)}


def delete_event(
    event_id: str,
    calendar_id: str = GOOGLE_CALENDAR_ID,
) -> dict:
    """Delete an event. Dangerous — always behind human approval."""
    event_id = (event_id or "").strip()
    if not event_id:
        return {"error": "event_id is required"}
    service = google_auth.get_service("calendar", "v3")
    try:
        service.events().delete(
            calendarId=calendar_id or GOOGLE_CALENDAR_ID,
            eventId=event_id,
            sendUpdates="all",
        ).execute()
    except Exception as exc:
        if HttpError is not None and isinstance(exc, HttpError):
            return _api_error(exc)
        raise
    return {"status": "event_deleted", "event_id": event_id}


def today_agenda(days: int = 1, calendar_id: str = GOOGLE_CALENDAR_ID) -> dict:
    """Convenience wrapper used by the daily brief."""
    return list_events(days=days, calendar_id=calendar_id)
