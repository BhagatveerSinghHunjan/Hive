"""Club-operations workflows for the student-club coordinator use case.

Each workflow is read-mostly: it gathers data from Gmail/Calendar/Tasks and
returns a brief plus ``next_actions``. Outbound actions (email sends, calendar
invites) are *never* executed here — the Leader executes them as separate tool
calls so the normal approval gate applies.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from hive.config import HIVE_TIMEZONE
from hive.integrations import calendar, gmail, tasks
from hive.integrations.google_auth import GoogleIntegrationError

logger = logging.getLogger(__name__)

CATEGORY_KEYWORDS = {
    "venue": ("venue", "auditorium", "hall", "booking", "room", "av ", "equipment"),
    "sponsor": ("sponsor", "sponsorship", "funding", "budget", "invoice", "grant"),
    "volunteer": ("volunteer", "shift", "roster", "sign-up", "signup", "helper"),
    "meeting": ("meeting", "agenda", "call", "sync", "schedule", "calendar"),
    "urgent": ("urgent", "asap", "today", "deadline", "final", "action required", "reminder"),
}

ACTIONABLE_CATEGORIES = {"venue", "sponsor", "meeting", "urgent"}


def _now() -> datetime:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(HIVE_TIMEZONE))
    except Exception:
        return datetime.now(timezone.utc)


def _today_iso() -> str:
    return _now().date().isoformat()


def _days_from_now(days: int) -> str:
    return (_now().date() + timedelta(days=days)).isoformat()


def _call_label(func) -> str:
    return getattr(func, "__name__", str(func))


async def _google(func, *args, **kwargs) -> dict:
    """Run a Google-backed helper off the event loop and normalize errors."""
    try:
        result = await asyncio.to_thread(func, *args, **kwargs)
    except GoogleIntegrationError as exc:
        return {
            "error": str(exc)[:400],
            "needs_auth": True,
            "setup_hint": "Run: python -m hive.cli --connect-google",
        }
    except Exception as exc:
        logger.warning("%s failed: %s", _call_label(func), exc)
        return {"error": str(exc)[:400], "error_type": type(exc).__name__}
    if isinstance(result, dict) and result.get("error"):
        return result
    return result


def _classify(subject: str, snippet: str, sender: str = "") -> list[str]:
    text = f"{sender} {subject} {snippet}".lower()
    return [
        category
        for category, keywords in CATEGORY_KEYWORDS.items()
        if any(keyword in text for keyword in keywords)
    ]


def _priority(categories: list[str], subject: str) -> str:
    subject_lower = (subject or "").lower()
    if "urgent" in categories or "action required" in subject_lower:
        return "high"
    if "sponsor" in categories or "venue" in categories:
        return "high"
    if "meeting" in categories or "volunteer" in categories:
        return "medium"
    return "low"


def _triage_item(message: dict) -> dict:
    subject = message.get("subject") or "(no subject)"
    snippet = message.get("snippet") or ""
    sender = message.get("from") or ""
    categories = _classify(subject, snippet, sender)
    return {
        "message_id": message.get("message_id"),
        "thread_id": message.get("thread_id"),
        "from": sender,
        "subject": subject,
        "date": message.get("date"),
        "snippet": snippet,
        "unread": message.get("unread", False),
        "categories": categories,
        "priority": _priority(categories, subject),
        "needs_reply": bool(set(categories) & ACTIONABLE_CATEGORIES),
    }


def _draft_action(to: str, subject: str, body: str, thread_id: str | None = None) -> dict:
    args = {"to": to, "subject": subject, "body": body}
    if thread_id:
        args["thread_id"] = thread_id
    return {
        "tool": "gmail_create_draft",
        "args": args,
        "reason": "Prepare a reply for human review (draft only — never auto-send).",
        "requires_approval": True,
    }


def _task_action(title: str, due: str | None = None, notes: str = "",
                 priority: str = "medium") -> dict:
    return {
        "tool": "task_add",
        "args": {"title": title, "due": due, "notes": notes, "priority": priority},
        "reason": "Capture the follow-up so it is not lost.",
        "requires_approval": False,
    }


def _text_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- (none)"


# ─── Workflows ──────────────────────────────────────────────────────────


async def triage_inbox(
    query: str = "is:unread newer_than:7d",
    max_results: int = 20,
    create_tasks: bool = False,
) -> dict:
    """Classify unread mail into club-ops categories with suggested replies."""
    search = await _google(gmail.search_messages, query, max_results)
    if search.get("error"):
        return {"workflow": "triage_inbox", "ok": False, **search}

    items = [_triage_item(message) for message in search.get("messages", [])]
    items.sort(key=lambda item: {"high": 0, "medium": 1, "low": 2}[item["priority"]])

    drafts = []
    for item in items:
        if item["priority"] != "high" or not item["needs_reply"]:
            continue
        topic = item["subject"]
        body = (
            f"Hi,\n\nThanks for reaching out about {topic!r}. "
            "I am checking the details with the club team and will confirm shortly.\n\n"
            "Best,\nAnanya\n"
        )
        drafts.append(_draft_action(item["from"], f"Re: {topic}", body, item["thread_id"]))

    suggested_tasks = []
    for item in items:
        if set(item["categories"]) & {"sponsor", "venue"}:
            suggested_tasks.append(_task_action(
                f"Follow up: {item['subject']}",
                due=_days_from_now(2),
                notes=f"From {item['from']} — {item['snippet'][:160]}",
                priority="high",
            ))

    created = []
    if create_tasks:
        for action in suggested_tasks:
            created.append(await _google(tasks.add_task, **action["args"]))

    counts: dict[str, int] = {}
    for item in items:
        for category in item["categories"] or ["general"]:
            counts[category] = counts.get(category, 0) + 1

    summary_lines = [
        f"Triaged {len(items)} message(s) from {query!r}.",
        "High priority: " + str(sum(1 for item in items if item["priority"] == "high")),
        "Categories: " + (", ".join(f"{k}={v}" for k, v in counts.items()) or "none"),
    ]

    return {
        "workflow": "triage_inbox",
        "ok": True,
        "query": query,
        "count": len(items),
        "counts": counts,
        "items": items,
        "suggested_drafts": drafts[:5],
        "suggested_tasks": suggested_tasks[:8],
        "tasks_created": created,
        "next_actions": (drafts[:3] + suggested_tasks[:3]),
        "summary": "\n".join(summary_lines),
    }


async def prepare_meeting(
    event_query: str | None = None,
    days: int = 7,
    max_emails: int = 5,
) -> dict:
    """Build a briefing packet for the next meeting (or a matching event)."""
    agenda = await _google(calendar.list_events, days=days)
    if agenda.get("error"):
        return {"workflow": "prepare_meeting", "ok": False, **agenda}

    events = agenda.get("events", [])
    event = None
    if event_query:
        needle = event_query.lower()
        event = next(
            (
                item for item in events
                if needle in (item.get("summary") or "").lower()
                or needle in (item.get("location") or "").lower()
            ),
            None,
        )
    if event is None and events:
        event = events[0]

    if event is None:
        return {
            "workflow": "prepare_meeting",
            "ok": False,
            "error": f"No meetings found in the next {days} day(s).",
            "events": [],
        }

    attendee_emails = [
        a.get("email") for a in event.get("attendees", []) if a.get("email")
    ]
    query_parts = []
    if attendee_emails:
        query_parts = [f"(from:{email} OR to:{email})" for email in attendee_emails[:2]]
    query = " OR ".join(query_parts) + " newer_than:30d" if query_parts else "newer_than:14d"

    emails = await _google(gmail.search_messages, query, max_emails)
    related = emails.get("messages", []) if not emails.get("error") else []

    open_questions = []
    if not attendee_emails:
        open_questions.append("No attendees listed — confirm who should attend.")
    if not event.get("location"):
        open_questions.append("No location/meeting link on the event.")
    if not event.get("description"):
        open_questions.append("No agenda in the event description.")

    suggested_agenda = [
        "Confirm logistics (venue/link, time, attendees)",
        "Review open email threads and decisions",
        "Assign owners for follow-ups",
        "Confirm next steps and deadlines",
    ]

    lines = [
        f"Meeting prep: {event.get('summary')}",
        f"When: {event.get('start')} → {event.get('end')}",
        f"Where: {event.get('location') or '(not set)'}",
        f"Attendees: {', '.join(attendee_emails) or '(none listed)'}",
        "",
        "Related email:",
    ]
    if related:
        lines += [
            f"- {m.get('subject')} — {m.get('from')} ({m.get('date')})"
            for m in related
        ]
    else:
        lines.append("- (none found)")

    return {
        "workflow": "prepare_meeting",
        "ok": True,
        "event": event,
        "related_emails": related,
        "open_questions": open_questions,
        "suggested_agenda": suggested_agenda,
        "next_actions": [
            _task_action(
                f"Prep for {event.get('summary')}",
                due=(event.get("start") or "")[:10] or _today_iso(),
                notes="; ".join(suggested_agenda[:3]),
                priority="high",
            )
        ],
        "summary": "\n".join(lines),
    }


async def post_meeting_followup(
    meeting_title: str,
    notes: str = "",
    attendees: str = "",
    due: str | None = None,
    create_tasks: bool = True,
) -> dict:
    """Turn meeting notes into follow-up tasks and a draft recap email."""
    title = (meeting_title or "").strip()
    if not title:
        return {"workflow": "post_meeting_followup", "ok": False,
                "error": "meeting_title is required"}

    due_date = due or _days_from_now(1)
    note_lines = [
        line.strip(" -•\t")
        for line in (notes or "").splitlines()
        if line.strip(" -•\t")
    ]
    decisions = [line for line in note_lines if line.lower().startswith(("decision", "decided"))]
    action_items = [
        line for line in note_lines
        if not line.lower().startswith(("decision", "decided"))
    ] or note_lines

    proposed_tasks = [
        _task_action(
            f"Follow up: {title}",
            due=due_date,
            notes="Meeting recap and action items.",
            priority="high",
        )
    ]
    for item in action_items[:5]:
        proposed_tasks.append(_task_action(
            item[:180], due=due_date, notes=f"From meeting: {title}", priority="medium"
        ))

    created = []
    if create_tasks:
        for action in proposed_tasks:
            created.append(await _google(tasks.add_task, **action["args"]))

    recipient = (attendees or "").strip()
    recap_body = (
        f"Hi all,\n\nThanks for joining {title!r}. Here is a quick recap:\n\n"
        + ("\n".join(f"- {line}" for line in note_lines) if note_lines else "- (add notes)")
        + f"\n\nNext step: I will follow up by {due_date}.\n\nBest,\nAnanya\n"
    )
    actions = []
    if recipient:
        actions.append(_draft_action(recipient, f"Recap: {title}", recap_body))

    summary = (
        f"Post-meeting follow-up for {title}\n"
        f"Tasks created: {len(created)}\n"
        f"Recap draft: {'ready to review' if actions else 'add attendee emails to draft'}"
    )
    return {
        "workflow": "post_meeting_followup",
        "ok": True,
        "meeting_title": title,
        "decisions": decisions,
        "action_items": action_items,
        "tasks_created": created,
        "suggested_tasks": proposed_tasks,
        "next_actions": actions + proposed_tasks[:3],
        "summary": summary,
    }


async def sponsor_reminders(days: int = 30, create_tasks: bool = False) -> dict:
    """Find sponsor threads that need a nudge and draft reminder emails."""
    query = "sponsor OR sponsorship OR funding newer_than:%dd" % max(1, days)
    search = await _google(gmail.search_messages, query, 20)
    if search.get("error"):
        return {"workflow": "sponsor_reminders", "ok": False, **search}

    messages = search.get("messages", [])
    sponsors = []
    actions = []
    for message in messages[:8]:
        subject = message.get("subject") or "(no subject)"
        sender = message.get("from") or ""
        snippet = message.get("snippet") or ""
        sponsors.append({
            "from": sender,
            "subject": subject,
            "date": message.get("date"),
            "snippet": snippet,
            "thread_id": message.get("thread_id"),
            "message_id": message.get("message_id"),
        })
        body = (
            "Hi,\n\nJust following up on our sponsorship conversation. "
            "We would love to confirm the next step and any materials you need from us.\n\n"
            "Best,\nAnanya\n"
        )
        actions.append(_draft_action(sender, f"Re: {subject}", body, message.get("thread_id")))

    proposed_tasks = [
        _task_action(
            f"Sponsor follow-up: {item['subject']}",
            due=_days_from_now(7),
            notes=item["snippet"][:160],
            priority="high",
        )
        for item in sponsors[:5]
    ]
    created = []
    if create_tasks:
        for action in proposed_tasks:
            created.append(await _google(tasks.add_task, **action["args"]))

    lines = [f"Found {len(sponsors)} sponsor-related thread(s)."]
    lines += [f"- {item['subject']} — {item['from']}" for item in sponsors[:6]]
    return {
        "workflow": "sponsor_reminders",
        "ok": True,
        "count": len(sponsors),
        "sponsors": sponsors,
        "suggested_drafts": actions[:5],
        "suggested_tasks": proposed_tasks,
        "tasks_created": created,
        "next_actions": actions[:3] + proposed_tasks[:3],
        "summary": "\n".join(lines),
    }


async def volunteer_schedule(
    event_title: str,
    volunteers: str = "",
    duration_minutes: int = 60,
    days: int = 7,
) -> dict:
    """Propose volunteer shifts from free calendar slots and draft the ask."""
    title = (event_title or "").strip() or "club event"
    slots_result = await _google(
        calendar.find_free_slots, duration_minutes, None, None, days
    )
    if slots_result.get("error"):
        return {"workflow": "volunteer_schedule", "ok": False, **slots_result}

    slots = slots_result.get("slots", [])
    emails = (volunteers or "").strip()
    search = await _google(gmail.search_messages, "volunteer newer_than:30d", 10)
    related = search.get("messages", []) if not search.get("error") else []

    slot_lines = [f"- {slot.get('display')}" for slot in slots[:5]] or ["- (no slots found)"]
    body = (
        f"Hi,\n\nWe are organising {title!r} and would love your help. "
        "Could you take one of these slots?\n\n"
        + "\n".join(slot_lines)
        + "\n\nThanks!\nAnanya\n"
    )
    actions = []
    if emails:
        actions.append(_draft_action(emails, f"Volunteer shifts: {title}", body))

    proposed_task = _task_action(
        f"Confirm volunteer shifts for {title}",
        due=_days_from_now(3),
        notes="Slots: " + "; ".join(slot.get("display", "") for slot in slots[:3]),
        priority="medium",
    )

    lines = [
        f"Volunteer scheduling for {title}",
        f"Free slots ({duration_minutes} min):",
        *slot_lines,
        f"Volunteer email draft: {'ready' if actions else 'add volunteer emails'}",
    ]
    return {
        "workflow": "volunteer_schedule",
        "ok": True,
        "event_title": title,
        "slots": slots,
        "related_volunteer_emails": related,
        "suggested_task": proposed_task,
        "next_actions": actions + [proposed_task],
        "summary": "\n".join(lines),
    }


async def venue_confirmation(
    venue_email: str | None = None,
    event_title: str | None = None,
    days: int = 21,
) -> dict:
    """Check venue threads and draft a confirmation request."""
    query = "venue OR auditorium OR booking OR confirmation newer_than:%dd" % max(1, days)
    search = await _google(gmail.search_messages, query, 15)
    if search.get("error"):
        return {"workflow": "venue_confirmation", "ok": False, **search}

    messages = search.get("messages", [])
    latest = messages[0] if messages else None
    thread_summary = None
    if latest and latest.get("thread_id"):
        thread = await _google(gmail.read_thread, latest["thread_id"], 2000)
        if not thread.get("error"):
            thread_summary = {
                "thread_id": thread.get("thread_id"),
                "subject": thread.get("subject"),
                "count": thread.get("count"),
                "latest_body": (thread.get("messages") or [{}])[-1].get("body", "")[:800],
            }

    recipient = (venue_email or (latest or {}).get("from") or "").strip()
    title = (event_title or (latest or {}).get("subject") or "the event").strip()
    body = (
        f"Hi,\n\nWe would like to confirm the venue booking for {title!r}. "
        "Could you confirm availability and the next step to lock it in?\n\n"
        "Thanks,\nAnanya\n"
    )
    actions = []
    if recipient:
        actions.append(_draft_action(recipient, f"Venue confirmation: {title}", body))

    task = _task_action(
        f"Confirm venue for {title}",
        due=_days_from_now(2),
        notes=(latest or {}).get("snippet", "")[:160],
        priority="high",
    )

    lines = [f"Venue threads found: {len(messages)}"]
    if latest:
        lines.append(f"Latest: {latest.get('subject')} — {latest.get('from')}")
    lines.append(f"Draft: {'ready' if actions else 'add a venue email'}")
    return {
        "workflow": "venue_confirmation",
        "ok": True,
        "count": len(messages),
        "messages": messages[:5],
        "latest_thread": thread_summary,
        "suggested_task": task,
        "next_actions": actions + [task],
        "summary": "\n".join(lines),
    }


async def daily_brief(days: int = 1) -> dict:
    """Morning brief: agenda, inbox pressure, due tasks, and nudges."""
    agenda, inbox, task_list = await asyncio.gather(
        _google(calendar.list_events, days=days),
        _google(gmail.search_messages, "is:unread newer_than:2d", 10),
        _google(tasks.list_tasks),
    )

    events = agenda.get("events", []) if not agenda.get("error") else []
    messages = inbox.get("messages", []) if not inbox.get("error") else []
    pending = task_list.get("tasks", []) if not task_list.get("error") else []
    due_soon = [
        t for t in pending
        if t.get("due") and t["due"] <= _days_from_now(2)
    ]

    errors = [
        label for label, result in (
            ("calendar", agenda), ("gmail", inbox), ("tasks", task_list)
        ) if result.get("error")
    ]

    lines = [
        f"Daily brief — {_today_iso()}",
        "",
        "Agenda:",
        *([f"- {e.get('start')}: {e.get('summary')}" for e in events[:6]] or ["- (clear)"]),
        "",
        f"Unread email: {len(messages)}",
        "Tasks due soon:",
        *([f"- {t.get('title')} (due {t.get('due')})" for t in due_soon[:6]] or ["- (none due)"]),
    ]
    if errors:
        lines += ["", f"Connectors needing attention: {', '.join(errors)}"]

    return {
        "workflow": "daily_brief",
        "ok": not errors or bool(events or messages or pending),
        "date": _today_iso(),
        "events": events,
        "unread": len(messages),
        "unread_messages": messages,
        "pending_tasks": pending,
        "due_soon": due_soon,
        "errors": errors,
        "next_actions": [
            _task_action(f"Review {len(messages)} unread emails", due=_today_iso()),
        ] if messages else [],
        "summary": "\n".join(lines),
    }


WORKFLOWS = {
    "triage_inbox": triage_inbox,
    "prepare_meeting": prepare_meeting,
    "post_meeting_followup": post_meeting_followup,
    "sponsor_reminders": sponsor_reminders,
    "volunteer_schedule": volunteer_schedule,
    "venue_confirmation": venue_confirmation,
    "daily_brief": daily_brief,
}


async def run_workflow(name: str, **params) -> dict:
    workflow = WORKFLOWS.get((name or "").strip())
    if workflow is None:
        return {"ok": False, "error": f"Unknown workflow: {name}"}
    return await workflow(**params)
