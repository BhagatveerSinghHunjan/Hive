"""Credential-safe snapshots for the desktop UI, Ink frontend, and CLI."""

from __future__ import annotations

import asyncio
import logging

from hive.config import HIVE_TIMEZONE
from hive.integrations import calendar, gmail, tasks
from hive.integrations.google_auth import GoogleIntegrationError
from hive.integrations.registry import _redact, integration_status
from hive.missions import list_missions
from hive.workflows.club_ops import _triage_item

logger = logging.getLogger(__name__)


async def _safe(func, *args, **kwargs) -> dict:
    try:
        result = await asyncio.to_thread(func, *args, **kwargs)
    except GoogleIntegrationError as exc:
        return {
            "ok": False,
            "error": _redact(str(exc)),
            "needs_auth": True,
            "setup_hint": "Run: python -m hive.cli --connect-google",
        }
    except Exception as exc:
        logger.warning("State API call %s failed: %s", getattr(func, "__name__", func), exc)
        return {"ok": False, "error": _redact(str(exc))}
    if isinstance(result, dict) and result.get("error"):
        return {"ok": False, **result}
    return {"ok": True, **result}


async def inbox(limit: int = 20, query: str = "is:unread newer_than:14d") -> dict:
    result = await _safe(gmail.search_messages, query, limit)
    if not result.get("ok"):
        return result
    items = [_triage_item(message) for message in result.get("messages", [])]
    items.sort(key=lambda item: {"high": 0, "medium": 1, "low": 2}[item["priority"]])
    return {
        "ok": True,
        "query": query,
        "count": len(items),
        "items": items,
    }


async def agenda(days: int = 7) -> dict:
    result = await _safe(calendar.list_events, days=days)
    if not result.get("ok"):
        return result
    return {
        "ok": True,
        "timezone": HIVE_TIMEZONE,
        "count": result.get("count", len(result.get("events", []))),
        "events": result.get("events", []),
    }


async def tasks_snapshot(include_completed: bool = False) -> dict:
    result = await _safe(tasks.list_tasks, None, include_completed, 100)
    if not result.get("ok"):
        return result
    status = await _safe(tasks.status)
    return {
        "ok": True,
        "count": result.get("count", 0),
        "pending": result.get("pending", 0),
        "tasks": result.get("tasks", []),
        "status": status if status.get("ok") else {},
    }


async def add_task(title: str, due: str | None = None, priority: str = "medium",
                   notes: str = "") -> dict:
    result = await _safe(tasks.add_task, title, notes, due, priority)
    if result.get("ok"):
        result["tasks"] = (await tasks_snapshot()).get("tasks", [])
    return result


async def complete_task(task_id: str) -> dict:
    result = await _safe(tasks.complete_task, task_id)
    if result.get("ok"):
        result["tasks"] = (await tasks_snapshot()).get("tasks", [])
    return result


async def missions() -> dict:
    listing = list_missions()
    return {"ok": True, **listing}


async def integrations(verify: bool = False) -> dict:
    try:
        status = await integration_status(verify=verify)
    except Exception as exc:
        return {"ok": False, "error": _redact(str(exc))}
    google = status.get("google")
    if isinstance(google, dict):
        google.pop("client_source", None)
    return {"ok": True, **status}


async def overview() -> dict:
    inbox_result, agenda_result, task_result, integration_result, mission_result = (
        await asyncio.gather(
            inbox(5),
            agenda(1),
            tasks_snapshot(),
            integrations(verify=False),
            missions(),
        )
    )
    events = agenda_result.get("events", []) if agenda_result.get("ok") else []
    task_items = task_result.get("tasks", []) if task_result.get("ok") else []
    due_soon = [t for t in task_items if t.get("due")]
    google = (integration_result.get("google") or {}) if integration_result.get("ok") else {}
    return {
        "ok": True,
        "timezone": HIVE_TIMEZONE,
        "inbox": {
            "ok": inbox_result.get("ok", False),
            "count": inbox_result.get("count", 0),
            "needs_auth": inbox_result.get("needs_auth", False),
            "items": inbox_result.get("items", [])[:5],
        },
        "agenda": {
            "ok": agenda_result.get("ok", False),
            "count": agenda_result.get("count", 0),
            "next": events[0] if events else None,
            "events": events[:3],
            "needs_auth": agenda_result.get("needs_auth", False),
        },
        "tasks": {
            "ok": task_result.get("ok", False),
            "pending": task_result.get("pending", 0),
            "due_soon": due_soon[:5],
        },
        "missions": mission_result.get("count", 0),
        "connections": {
            "google_connected": google.get("connected", False),
            "google_email": google.get("email"),
            "slack_configured": (integration_result.get("slack") or {}).get(
                "configured", False
            ),
        },
    }


async def draft_reply(
    thread_id: str,
    body: str | None = None,
    to: str | None = None,
    subject: str | None = None,
) -> dict:
    """User-initiated draft creation from an inbox thread (never sends)."""
    thread_id = (thread_id or "").strip()
    if not thread_id:
        return {"ok": False, "error": "thread_id is required"}

    thread = await _safe(gmail.read_thread, thread_id, 4000)
    if not thread.get("ok"):
        return thread

    messages = thread.get("messages") or []
    latest = messages[-1] if messages else {}
    recipient = to or latest.get("from") or ""
    subject_line = subject or thread.get("subject") or "(no subject)"
    if not subject_line.lower().startswith("re:"):
        subject_line = f"Re: {subject_line}"
    draft_body = body or (
        "Hi,\n\nThanks for the note — I am looking into this and will "
        "confirm the details shortly.\n\nBest,\nAnanya\n"
    )
    result = await _safe(
        gmail.create_draft,
        recipient,
        subject_line,
        draft_body,
        None,
        None,
        thread_id,
        latest.get("message_id_header"),
    )
    if result.get("ok"):
        result["draft_only"] = True
    return result


# ─── Text renderers (CLI / server slash commands) ───────────────────────


def format_inbox_text(data: dict, limit: int = 8) -> str:
    if not data.get("ok"):
        return f"Inbox unavailable: {data.get('error', 'unknown error')}"
    lines = [f"Inbox — {data.get('count', 0)} unread"]
    for item in data.get("items", [])[:limit]:
        tags = ", ".join(item.get("categories") or []) or "general"
        lines.append(
            f"- [{item.get('priority')}] {item.get('subject')} — {item.get('from')} ({tags})"
        )
        if item.get("snippet"):
            lines.append(f"  {item['snippet'][:140]}")
    return "\n".join(lines)


def format_agenda_text(data: dict, limit: int = 10) -> str:
    if not data.get("ok"):
        return f"Calendar unavailable: {data.get('error', 'unknown error')}"
    lines = [f"Agenda — {data.get('count', 0)} event(s)"]
    for event in data.get("events", [])[:limit]:
        lines.append(
            f"- {event.get('start')} → {event.get('end')}: {event.get('summary')}"
            + (f" @ {event.get('location')}" if event.get("location") else "")
        )
    return "\n".join(lines)


def format_tasks_text(data: dict, limit: int = 12) -> str:
    if not data.get("ok"):
        return f"Tasks unavailable: {data.get('error', 'unknown error')}"
    lines = [f"Tasks — {data.get('pending', 0)} pending / {data.get('count', 0)} shown"]
    for task in data.get("tasks", [])[:limit]:
        due = f" (due {task['due']})" if task.get("due") else ""
        marker = "[x]" if task.get("status") == "done" else "[ ]"
        lines.append(f"{marker} {task.get('task_id')} · {task.get('title')}{due}")
    return "\n".join(lines)


def format_overview_text(data: dict) -> str:
    inbox = data.get("inbox", {})
    agenda = data.get("agenda", {})
    tasks_info = data.get("tasks", {})
    connections = data.get("connections", {})
    next_event = agenda.get("next") or {}
    lines = [
        f"Unread email: {inbox.get('count', 0)}",
        f"Next meeting: {next_event.get('summary') or '(none)'}",
        f"Pending tasks: {tasks_info.get('pending', 0)}",
        f"Missions: {data.get('missions', 0)}",
        f"Google: {'connected' if connections.get('google_connected') else 'not connected'}",
    ]
    return "\n".join(lines)
