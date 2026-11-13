"""Mission templates — named, parameterized workflows.

Built-ins cover the student-club coordinator case study. Custom missions can be
dropped into ``~/.hive/missions/*.json``:

    {
      "name": "weekly_sponsor_check",
      "title": "Weekly sponsor check",
      "description": "Review sponsor threads and prep nudges",
      "workflow": "sponsor_reminders",
      "params": {"days": 14},
      "param_descriptions": {"days": "Lookback window"}
    }
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from hive.config import HIVE_HOME
from hive.workflows.club_ops import WORKFLOWS

logger = logging.getLogger(__name__)

MISSIONS_DIR = HIVE_HOME / "missions"


BUILTIN_MISSIONS: dict[str, dict] = {
    "morning_brief": {
        "title": "Morning brief",
        "description": "Agenda, unread email, and tasks due soon.",
        "workflow": "daily_brief",
        "params": {"days": 1},
        "param_types": {"days": "int"},
    },
    "inbox_triage": {
        "title": "Inbox triage",
        "description": "Classify unread club email and propose replies/tasks.",
        "workflow": "triage_inbox",
        "params": {"query": "is:unread newer_than:7d", "max_results": 20},
        "param_types": {"max_results": "int", "create_tasks": "bool"},
    },
    "meeting_prep": {
        "title": "Meeting prep",
        "description": "Briefing packet for the next meeting.",
        "workflow": "prepare_meeting",
        "params": {"days": 7},
        "param_types": {"days": "int", "max_emails": "int"},
    },
    "post_meeting_followup": {
        "title": "Post-meeting follow-up",
        "description": "Tasks plus recap email draft from meeting notes.",
        "workflow": "post_meeting_followup",
        "params": {"notes": "", "attendees": "", "create_tasks": True},
        "param_types": {"create_tasks": "bool"},
        "required": ["meeting_title"],
    },
    "sponsor_followups": {
        "title": "Sponsor follow-ups",
        "description": "Draft nudges for sponsor threads and capture tasks.",
        "workflow": "sponsor_reminders",
        "params": {"days": 30},
        "param_types": {"days": "int", "create_tasks": "bool"},
    },
    "volunteer_scheduling": {
        "title": "Volunteer scheduling",
        "description": "Propose shifts and draft the volunteer email.",
        "workflow": "volunteer_schedule",
        "params": {"duration_minutes": 60, "days": 7},
        "param_types": {"duration_minutes": "int", "days": "int"},
        "required": ["event_title"],
    },
    "venue_confirmation": {
        "title": "Venue confirmation",
        "description": "Check venue threads and draft the confirmation email.",
        "workflow": "venue_confirmation",
        "params": {"days": 21},
        "param_types": {"days": "int"},
    },
    "weekly_review": {
        "title": "Weekly review",
        "description": "Seven-day agenda, inbox pressure, and due tasks.",
        "workflow": "daily_brief",
        "params": {"days": 7},
        "param_types": {"days": "int"},
    },
}


def _custom_missions() -> dict[str, dict]:
    missions: dict[str, dict] = {}
    directory = Path(MISSIONS_DIR)
    if not directory.exists():
        return missions
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Skipping invalid mission %s: %s", path.name, exc)
            continue
        name = str(data.get("name") or path.stem).strip()
        workflow = str(data.get("workflow") or "").strip()
        if not name or workflow not in WORKFLOWS:
            logger.warning("Skipping mission %s: unknown workflow %r", name, workflow)
            continue
        missions[name] = {
            "title": data.get("title") or name.replace("_", " ").title(),
            "description": data.get("description", ""),
            "workflow": workflow,
            "params": data.get("params") or {},
            "param_types": data.get("param_types") or {},
            "required": data.get("required") or [],
            "source": "custom",
        }
    return missions


def all_missions() -> dict[str, dict]:
    missions = {
        name: {**spec, "source": "builtin"}
        for name, spec in BUILTIN_MISSIONS.items()
    }
    missions.update(_custom_missions())
    return missions


def list_missions() -> dict:
    missions = all_missions()
    return {
        "count": len(missions),
        "missions": [
            {
                "name": name,
                "title": spec["title"],
                "description": spec.get("description", ""),
                "workflow": spec["workflow"],
                "params": spec.get("params", {}),
                "required": spec.get("required", []),
                "source": spec.get("source", "builtin"),
            }
            for name, spec in sorted(missions.items())
        ],
    }


def _coerce(value, kind: str):
    if kind == "int":
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    if kind == "bool":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "on")
    return value


async def run_mission(name: str, params: dict | None = None) -> dict:
    missions = all_missions()
    spec = missions.get((name or "").strip())
    if spec is None:
        return {
            "ok": False,
            "error": f"Unknown mission: {name}",
            "available": sorted(missions),
        }

    merged = dict(spec.get("params") or {})
    for key, value in (params or {}).items():
        merged[key] = value

    missing = [key for key in spec.get("required", []) if not merged.get(key)]
    if missing:
        return {
            "ok": False,
            "error": f"Missing required parameters: {', '.join(missing)}",
            "mission": name,
            "required": spec.get("required", []),
        }

    types = spec.get("param_types") or {}
    merged = {key: _coerce(value, types.get(key, "str")) for key, value in merged.items()}

    workflow = WORKFLOWS[spec["workflow"]]
    allowed = set(workflow.__code__.co_varnames[: workflow.__code__.co_argcount])
    filtered = {key: value for key, value in merged.items() if key in allowed}

    result = await workflow(**filtered)
    return {
        "mission": name,
        "title": spec.get("title", name),
        "workflow": spec["workflow"],
        **result,
    }


def format_missions_text() -> str:
    listing = list_missions()
    lines = [f"Missions ({listing['count']}):"]
    for mission in listing["missions"]:
        source = "custom" if mission["source"] == "custom" else "built-in"
        required = ", ".join(mission["required"])
        suffix = f" · required: {required}" if required else ""
        lines.append(f"- {mission['name']} — {mission['description']} ({source}){suffix}")
    lines.append("Run with: /mission <name> key=value ...")
    return "\n".join(lines)
