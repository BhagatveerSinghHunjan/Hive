"""Club-ops workflows, missions, and tool registration tests."""

import asyncio

from hive.integrations import calendar as calendar_module
from hive.integrations import gmail as gmail_module
from hive.integrations import tasks as tasks_module
from hive.missions import list_missions, run_mission
from hive.permissions import get_tool_tier
from hive.tools import TOOLS
from hive.workflows import club_ops


def _messages():
    return {
        "count": 3,
        "messages": [
            {
                "message_id": "m1",
                "thread_id": "t1",
                "from": "Venue <venue@example.com>",
                "subject": "Auditorium booking — urgent confirmation",
                "snippet": "Can you confirm the venue for Friday?",
                "date": "Tue, 14 Nov 2026 10:00:00 +0530",
                "unread": True,
            },
            {
                "message_id": "m2",
                "thread_id": "t2",
                "from": "Sponsor <sponsor@acme.com>",
                "subject": "Sponsorship deck",
                "snippet": "Please send the updated sponsor deck.",
                "date": "Mon, 13 Nov 2026 09:00:00 +0530",
                "unread": True,
            },
            {
                "message_id": "m3",
                "thread_id": "t3",
                "from": "Newsletter <news@example.com>",
                "subject": "Weekly roundup",
                "snippet": "Club news and events.",
                "date": "Sun, 12 Nov 2026 08:00:00 +0530",
                "unread": True,
            },
        ],
    }


def _events():
    return {
        "count": 1,
        "events": [{
            "event_id": "e1",
            "summary": "Venue walkthrough",
            "start": "2026-11-18T15:00:00+05:30",
            "end": "2026-11-18T16:00:00+05:30",
            "location": "Auditorium",
            "description": "Check AV and seating",
            "attendees": [{"email": "venue@example.com", "status": "accepted"}],
        }],
    }


def test_workflow_tools_registered_with_tiers():
    expected = {
        "workflow_triage_inbox": "safe",
        "workflow_prepare_meeting": "safe",
        "workflow_daily_brief": "safe",
        "workflow_post_meeting_followup": "moderate",
        "workflow_venue_confirmation": "safe",
        "mission_list": "safe",
        "mission_run": "moderate",
    }
    for name, tier in expected.items():
        assert name in TOOLS
        assert get_tool_tier(name) == tier


def test_triage_inbox_classifies_and_proposes(monkeypatch):
    monkeypatch.setattr(gmail_module, "search_messages", lambda q, n: _messages())
    result = asyncio.run(club_ops.triage_inbox())
    assert result["ok"] is True
    assert result["count"] == 3
    priorities = [item["priority"] for item in result["items"]]
    assert priorities[0] == "high"
    assert result["items"][0]["categories"]
    assert result["suggested_drafts"]
    assert result["suggested_drafts"][0]["requires_approval"] is True


def test_prepare_meeting_briefing(monkeypatch):
    monkeypatch.setattr(calendar_module, "list_events", lambda **kw: _events())
    monkeypatch.setattr(gmail_module, "search_messages", lambda q, n: _messages())
    result = asyncio.run(club_ops.prepare_meeting(event_query="venue"))
    assert result["ok"] is True
    assert result["event"]["summary"] == "Venue walkthrough"
    assert "Meeting prep" in result["summary"]
    assert result["suggested_agenda"]
    assert result["next_actions"][0]["tool"] == "task_add"


def test_post_meeting_followup_creates_tasks(monkeypatch, tmp_path):
    monkeypatch.setattr(tasks_module, "HIVE_TASKS_FILE", tmp_path / "tasks.json")
    result = asyncio.run(club_ops.post_meeting_followup(
        "Venue walkthrough",
        notes="Decision: book Friday\nOrder extra chairs\nConfirm AV",
        attendees="venue@example.com,advisor@example.com",
    ))
    assert result["ok"] is True
    assert len(result["tasks_created"]) == 3
    assert result["next_actions"][0]["tool"] == "gmail_create_draft"
    assert "Recap" in result["next_actions"][0]["args"]["subject"]


def test_venue_confirmation_returns_draft(monkeypatch):
    monkeypatch.setattr(gmail_module, "search_messages", lambda q, n: _messages())
    monkeypatch.setattr(
        gmail_module,
        "read_thread",
        lambda thread_id, chars: {
            "thread_id": thread_id,
            "subject": "Auditorium booking — urgent confirmation",
            "count": 1,
            "messages": [{"body": "Available Friday.", "from": "venue@example.com"}],
        },
    )
    result = asyncio.run(club_ops.venue_confirmation(event_title="Club fest"))
    assert result["ok"] is True
    assert result["latest_thread"]["thread_id"] == "t1"
    assert result["next_actions"][0]["tool"] == "gmail_create_draft"
    assert result["next_actions"][0]["requires_approval"] is True


def test_daily_brief_combines_connectors(monkeypatch):
    monkeypatch.setattr(calendar_module, "list_events", lambda **kw: _events())
    monkeypatch.setattr(gmail_module, "search_messages", lambda q, n: _messages())
    monkeypatch.setattr(
        tasks_module,
        "list_tasks",
        lambda *a, **kw: {"count": 1, "pending": 1, "tasks": [
            {"task_id": "task_1", "title": "Confirm venue",
             "due": club_ops._days_from_now(1), "status": "pending"}
        ]},
    )
    result = asyncio.run(club_ops.daily_brief())
    assert result["ok"] is True
    assert result["unread"] == 3
    assert result["events"][0]["summary"] == "Venue walkthrough"
    assert result["due_soon"][0]["title"] == "Confirm venue"


def test_missions_listing_and_run(monkeypatch):
    listing = list_missions()
    assert listing["count"] >= 7
    names = {m["name"] for m in listing["missions"]}
    assert {"morning_brief", "inbox_triage", "venue_confirmation"} <= names

    monkeypatch.setattr(gmail_module, "search_messages", lambda q, n: _messages())
    result = asyncio.run(run_mission("inbox_triage", {"max_results": 10}))
    assert result["mission"] == "inbox_triage"
    assert result["ok"] is True
    assert result["count"] == 3


def test_mission_requires_parameters():
    result = asyncio.run(run_mission("volunteer_scheduling", {}))
    assert result["ok"] is False
    assert "event_title" in result["error"]


def test_unknown_mission():
    result = asyncio.run(run_mission("nope", {}))
    assert result["ok"] is False
    assert "available" in result


def test_android_style_custom_mission_loading(monkeypatch, tmp_path):
    import json

    from hive import missions as missions_module

    mission_dir = tmp_path / "missions"
    mission_dir.mkdir()
    (mission_dir / "custom.json").write_text(json.dumps({
        "name": "custom_brief",
        "title": "Custom brief",
        "workflow": "daily_brief",
        "params": {"days": 2},
        "param_types": {"days": "int"},
    }), encoding="utf-8")
    monkeypatch.setattr(missions_module, "MISSIONS_DIR", mission_dir)
    listing = missions_module.list_missions()
    custom = next(m for m in listing["missions"] if m["name"] == "custom_brief")
    assert custom["source"] == "custom"
