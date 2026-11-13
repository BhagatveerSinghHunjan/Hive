"""Task tracking for club operations.

Local ``~/.hive/tasks.json`` is the source of truth. When Google is connected,
:func:`sync` mirrors tasks to/from Google Tasks (optional, never required).
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from hive.config import (
    GOOGLE_TASKS_LIST_ID,
    HIVE_GOOGLE_TASKS_SYNC,
    HIVE_TASKS_FILE,
)
from hive.integrations.google_auth import google_auth

try:
    from googleapiclient.errors import HttpError
except Exception:  # pragma: no cover - optional dependency
    HttpError = None

logger = logging.getLogger(__name__)

VALID_STATUSES = {"pending", "done", "cancelled"}
VALID_PRIORITIES = {"low", "medium", "high"}
MAX_TASKS = 500


def _tasks_path() -> Path:
    path = Path(HIVE_TASKS_FILE).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> list[dict]:
    path = _tasks_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read tasks file: %s", exc)
        return []
    if isinstance(data, dict):
        data = data.get("tasks", [])
    if not isinstance(data, list):
        return []
    return [t for t in data if isinstance(t, dict)]


def _save(tasks: list[dict]) -> None:
    path = _tasks_path()
    payload = {"version": 1, "tasks": tasks[:MAX_TASKS]}
    fd, tmp = tempfile.mkstemp(prefix=".tasks-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _normalize_due(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).date().isoformat()
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%b %d %Y", "%d %b %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _public(task: dict) -> dict:
    return {
        "task_id": task.get("id"),
        "title": task.get("title", ""),
        "notes": task.get("notes", ""),
        "due": task.get("due"),
        "priority": task.get("priority", "medium"),
        "status": task.get("status", "pending"),
        "source": task.get("source", "local"),
        "google_task_id": task.get("google_task_id"),
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
        "completed_at": task.get("completed_at"),
    }


def add_task(
    title: str,
    notes: str = "",
    due: str | None = None,
    priority: str = "medium",
    source: str = "local",
) -> dict:
    title = (title or "").strip()
    if not title:
        return {"error": "title is required"}
    priority = (priority or "medium").strip().lower()
    if priority not in VALID_PRIORITIES:
        priority = "medium"

    now = _now_iso()
    task = {
        "id": f"task_{uuid.uuid4().hex[:10]}",
        "title": title[:300],
        "notes": str(notes or "")[:4000],
        "due": _normalize_due(due),
        "priority": priority,
        "status": "pending",
        "source": source or "local",
        "google_task_id": None,
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        "dirty": True,
    }
    tasks = _load()
    tasks.insert(0, task)
    _save(tasks)
    return {"status": "task_added", "task": _public(task), "count": len(tasks)}


def list_tasks(
    status: str | None = None,
    include_completed: bool = False,
    limit: int = 50,
) -> dict:
    tasks = _load()
    if status and status in VALID_STATUSES:
        filtered = [t for t in tasks if t.get("status") == status]
    elif include_completed:
        filtered = tasks
    else:
        filtered = [t for t in tasks if t.get("status") != "done"]
    filtered.sort(key=lambda t: (t.get("status") == "done", t.get("due") or "9999-12-31"))
    limited = filtered[: max(1, int(limit or 50))]
    pending = sum(1 for t in tasks if t.get("status") == "pending")
    return {
        "count": len(filtered),
        "pending": pending,
        "tasks": [_public(t) for t in limited],
    }


def _find(tasks: list[dict], task_id: str) -> tuple[int, dict] | tuple[None, None]:
    for index, task in enumerate(tasks):
        if task.get("id") == task_id or task.get("google_task_id") == task_id:
            return index, task
    return None, None


def update_task(
    task_id: str,
    title: str | None = None,
    notes: str | None = None,
    due: str | None = None,
    priority: str | None = None,
    status: str | None = None,
) -> dict:
    tasks = _load()
    index, task = _find(tasks, (task_id or "").strip())
    if task is None:
        return {"error": f"task not found: {task_id}"}

    if title is not None:
        cleaned = str(title).strip()
        if not cleaned:
            return {"error": "title cannot be empty"}
        task["title"] = cleaned[:300]
    if notes is not None:
        task["notes"] = str(notes)[:4000]
    if due is not None:
        normalized = _normalize_due(due)
        if normalized is None and str(due).strip():
            return {"error": f"could not parse due date: {due!r}"}
        task["due"] = normalized
    if priority is not None:
        priority = str(priority).strip().lower()
        if priority not in VALID_PRIORITIES:
            return {"error": f"priority must be one of {sorted(VALID_PRIORITIES)}"}
        task["priority"] = priority
    if status is not None:
        status = str(status).strip().lower()
        if status not in VALID_STATUSES:
            return {"error": f"status must be one of {sorted(VALID_STATUSES)}"}
        task["status"] = status
        task["completed_at"] = _now_iso() if status == "done" else None

    task["updated_at"] = _now_iso()
    task["dirty"] = True
    tasks[index] = task
    _save(tasks)
    return {"status": "task_updated", "task": _public(task)}


def complete_task(task_id: str) -> dict:
    return update_task(task_id, status="done")


def delete_task(task_id: str) -> dict:
    tasks = _load()
    index, task = _find(tasks, (task_id or "").strip())
    if task is None:
        return {"error": f"task not found: {task_id}"}
    removed = tasks.pop(index)
    _save(tasks)
    return {"status": "task_deleted", "task": _public(removed)}


def _google_tasks_service():
    return google_auth.get_service("tasks", "v1")


def _g_error(exc: Exception) -> dict:
    status = getattr(getattr(exc, "resp", None), "status", None)
    return {
        "error": str(exc)[:400],
        "status_code": status,
        "needs_auth": status in (401, 403),
        "setup_hint": (
            "Reconnect Google and allow the Tasks scope: "
            "python -m hive.cli --connect-google"
        ) if status in (401, 403) else None,
    }


def _remote_due(task: dict) -> str:
    due = task.get("due")
    if not due:
        return ""
    return f"{due}T00:00:00.000Z"


def _local_due(remote: dict) -> str | None:
    raw = remote.get("due")
    if not raw:
        return None
    try:
        return raw[:10]
    except Exception:
        return None


def sync(pull: bool = True, push: bool = True) -> dict:
    """Mirror local tasks with Google Tasks.

    Local always wins for dirty tasks. Remote changes are only accepted for
    tasks that have no unsynced local edits.
    """
    tasks = _load()
    pushed = 0
    pulled = 0
    updated = 0
    errors: list[str] = []

    try:
        service = _google_tasks_service()
        tasklists = service.tasklists().list(maxResults=100).execute().get("items", [])
        list_id = GOOGLE_TASKS_LIST_ID
        remote_items: list[dict] = []
        if list_id == "@default" and tasklists:
            list_id = tasklists[0].get("id", "@default")
        if pull:
            remote_items = (
                service.tasks()
                .list(
                    tasklist=list_id,
                    showCompleted=True,
                    showHidden=True,
                    maxResults=100,
                )
                .execute()
                .get("items", [])
                or []
            )
    except Exception as exc:
        if HttpError is not None and isinstance(exc, HttpError):
            return _g_error(exc)
        raise

    by_google_id = {t.get("google_task_id"): t for t in tasks if t.get("google_task_id")}

    if pull:
        for remote in remote_items:
            gid = remote.get("id")
            if not gid:
                continue
            status = "done" if remote.get("status") == "completed" else "pending"
            existing = by_google_id.get(gid)
            if existing is None:
                now = _now_iso()
                tasks.append({
                    "id": f"task_{uuid.uuid4().hex[:10]}",
                    "title": (remote.get("title") or "(untitled)")[:300],
                    "notes": (remote.get("notes") or "")[:4000],
                    "due": _local_due(remote),
                    "priority": "medium",
                    "status": status,
                    "source": "google",
                    "google_task_id": gid,
                    "created_at": now,
                    "updated_at": now,
                    "completed_at": now if status == "done" else None,
                    "dirty": False,
                })
                pulled += 1
            elif not existing.get("dirty"):
                changed = False
                title = (remote.get("title") or "").strip()
                if title and title != existing.get("title"):
                    existing["title"] = title[:300]
                    changed = True
                if status != existing.get("status") and existing.get("status") != "cancelled":
                    existing["status"] = status
                    changed = True
                due = _local_due(remote)
                if due != existing.get("due"):
                    existing["due"] = due
                    changed = True
                if changed:
                    existing["updated_at"] = _now_iso()
                    updated += 1

    if push:
        local_list_id = list_id
        try:
            for task in tasks:
                if not task.get("dirty"):
                    continue
                if task.get("status") == "cancelled":
                    if task.get("google_task_id"):
                        service.tasks().delete(
                            tasklist=local_list_id, task=task["google_task_id"]
                        ).execute()
                    task["dirty"] = False
                    continue
                body = {
                    "title": task.get("title", ""),
                    "notes": task.get("notes", ""),
                    "status": "completed" if task.get("status") == "done" else "needsAction",
                }
                due = _remote_due(task)
                if due:
                    body["due"] = due
                if task.get("google_task_id"):
                    service.tasks().patch(
                        tasklist=local_list_id,
                        task=task["google_task_id"],
                        body=body,
                    ).execute()
                else:
                    created = (
                        service.tasks()
                        .insert(tasklist=local_list_id, body=body)
                        .execute()
                    )
                    task["google_task_id"] = created.get("id")
                    task["source"] = "google"
                task["dirty"] = False
                task["updated_at"] = _now_iso()
                pushed += 1
        except Exception as exc:
            if HttpError is not None and isinstance(exc, HttpError):
                return _g_error(exc)
            errors.append(str(exc)[:200])

    _save(tasks)
    return {
        "status": "synced",
        "pushed": pushed,
        "pulled": pulled,
        "updated": updated,
        "errors": errors,
        "sync_enabled": HIVE_GOOGLE_TASKS_SYNC,
    }


def status() -> dict:
    tasks = _load()
    pending = sum(1 for t in tasks if t.get("status") == "pending")
    done = sum(1 for t in tasks if t.get("status") == "done")
    return {
        "mode": "local+google-sync" if HIVE_GOOGLE_TASKS_SYNC else "local",
        "count": len(tasks),
        "pending": pending,
        "done": done,
        "google_sync_enabled": HIVE_GOOGLE_TASKS_SYNC,
    }
