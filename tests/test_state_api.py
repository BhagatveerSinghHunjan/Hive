"""State API snapshots and desktop server protocol tests."""

import asyncio

from hive import state_api
from hive.integrations import calendar as calendar_module
from hive.integrations import gmail as gmail_module
from hive.integrations import tasks as tasks_module


def _search_result():
    return {
        "count": 1,
        "messages": [{
            "message_id": "m1",
            "thread_id": "t1",
            "from": "Venue <venue@example.com>",
            "subject": "Auditorium booking",
            "snippet": "Confirm Friday?",
            "date": "Tue, 14 Nov 2026 10:00:00 +0530",
            "unread": True,
        }],
    }


def _events_result():
    return {
        "count": 1,
        "events": [{
            "event_id": "e1",
            "summary": "Venue walkthrough",
            "start": "2026-11-18T15:00:00+05:30",
            "end": "2026-11-18T16:00:00+05:30",
            "location": "Auditorium",
            "attendees": [],
        }],
    }


def test_inbox_snapshot(monkeypatch):
    monkeypatch.setattr(gmail_module, "search_messages", lambda q, n: _search_result())
    result = asyncio.run(state_api.inbox())
    assert result["ok"] is True
    assert result["count"] == 1
    assert result["items"][0]["priority"] == "high"
    assert "venue" in result["items"][0]["categories"]


def test_agenda_and_tasks_snapshots(monkeypatch, tmp_path):
    monkeypatch.setattr(calendar_module, "list_events", lambda **kw: _events_result())
    monkeypatch.setattr(tasks_module, "HIVE_TASKS_FILE", tmp_path / "tasks.json")
    agenda = asyncio.run(state_api.agenda(3))
    assert agenda["ok"] is True
    assert agenda["events"][0]["summary"] == "Venue walkthrough"

    tasks_module.add_task("Confirm venue", due="2026-11-16")
    snapshot = asyncio.run(state_api.tasks_snapshot())
    assert snapshot["ok"] is True
    assert snapshot["pending"] == 1
    assert snapshot["status"]["mode"] == "local"


def test_add_and_complete_task_snapshot(monkeypatch, tmp_path):
    monkeypatch.setattr(tasks_module, "HIVE_TASKS_FILE", tmp_path / "tasks.json")
    added = asyncio.run(state_api.add_task("Email sponsor", due="2026-11-20"))
    assert added["ok"] is True
    task_id = added["task"]["task_id"]
    assert added["tasks"][0]["task_id"] == task_id

    completed = asyncio.run(state_api.complete_task(task_id))
    assert completed["ok"] is True
    assert completed["task"]["status"] == "done"


def test_draft_reply_creates_draft_only(monkeypatch):
    calls = {}

    def _read(thread_id, chars):
        return {
            "thread_id": thread_id,
            "subject": "Auditorium booking",
            "messages": [{
                "from": "venue@example.com",
                "message_id_header": "<m1@example.com>",
                "body": "Confirm Friday?",
            }],
        }

    def _draft(to, subject, body, cc, bcc, thread_id, in_reply_to):
        calls.update({
            "to": to, "subject": subject, "body": body,
            "thread_id": thread_id, "in_reply_to": in_reply_to,
        })
        return {"draft_id": "d1", "thread_id": thread_id, "status": "draft_created"}

    monkeypatch.setattr(gmail_module, "read_thread", _read)
    monkeypatch.setattr(gmail_module, "create_draft", _draft)
    result = asyncio.run(state_api.draft_reply("t1"))
    assert result["ok"] is True
    assert result["draft_only"] is True
    assert calls["to"] == "venue@example.com"
    assert calls["subject"].startswith("Re:")
    assert calls["in_reply_to"] == "<m1@example.com>"
    assert calls["thread_id"] == "t1"


def test_overview_shape(monkeypatch):
    monkeypatch.setattr(gmail_module, "search_messages", lambda q, n: _search_result())
    monkeypatch.setattr(calendar_module, "list_events", lambda **kw: _events_result())
    result = asyncio.run(state_api.overview())
    assert result["ok"] is True
    assert result["inbox"]["count"] == 1
    assert result["agenda"]["next"]["summary"] == "Venue walkthrough"
    assert "connections" in result


class _ServerCapture:
    def __init__(self):
        self.messages = []

    def _send(self, msg):
        self.messages.append(msg)

    async def _recv_async(self):
        return None


def test_server_request_protocol(monkeypatch):
    from hive.cli import HiveServer

    async def fake_inbox(limit=20, query=""):
        return {"ok": True, "count": 1, "items": [], "query": query}

    monkeypatch.setattr(state_api, "inbox", fake_inbox)
    server = HiveServer.__new__(HiveServer)
    server._pending_permissions = {}
    server._pending_interactive = {}
    server._send = _ServerCapture._send.__get__(server)
    server.messages = []

    asyncio.run(server._handle_request({
        "type": "request",
        "request_id": "r1",
        "action": "inbox",
        "params": {"limit": 5},
    }))
    response = server.messages[-1]
    assert response["type"] == "response"
    assert response["request_id"] == "r1"
    assert response["ok"] is True
    assert response["data"]["count"] == 1


def test_server_slash_command_routing(monkeypatch):
    from hive.cli import HiveServer

    async def fake_missions():
        return {"ok": True, "count": 2, "missions": []}

    monkeypatch.setattr(state_api, "missions", fake_missions)
    server = HiveServer.__new__(HiveServer)
    server._pending_permissions = {}
    server._pending_interactive = {}
    server.messages = []
    server._send = lambda msg: server.messages.append(msg)

    result = asyncio.run(server._handle_server_slash("/missions"))
    assert "Missions" in result

    asyncio.run(server._handle_server_slash_command("/help"))
    assert server.messages[-1]["type"] == "response"
    assert "/brief" in server.messages[-1]["content"]
