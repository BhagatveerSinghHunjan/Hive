"""Local task store + Google Tasks sync tests."""

from hive.integrations import tasks as tasks_module
from hive.permissions import get_tool_tier
from hive.tools import TOOLS


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(tasks_module, "HIVE_TASKS_FILE", tmp_path / "tasks.json")


def test_task_tools_registered_with_tiers():
    expected = {
        "task_add": "moderate",
        "task_list": "safe",
        "task_update": "moderate",
        "task_complete": "moderate",
        "task_delete": "moderate",
        "tasks_sync": "moderate",
    }
    for name, tier in expected.items():
        assert name in TOOLS
        assert get_tool_tier(name) == tier


def test_add_list_update_complete_delete(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    created = tasks_module.add_task(
        "Email venue about Friday", notes="Ask about AV", due="2026-12-04",
        priority="high",
    )
    assert created["status"] == "task_added"
    task_id = created["task"]["task_id"]
    assert created["task"]["due"] == "2026-12-04"
    assert created["task"]["priority"] == "high"

    listed = tasks_module.list_tasks()
    assert listed["count"] == 1
    assert listed["tasks"][0]["title"] == "Email venue about Friday"

    updated = tasks_module.update_task(task_id, title="Call venue", due="2026-12-03")
    assert updated["task"]["title"] == "Call venue"
    assert updated["task"]["due"] == "2026-12-03"

    completed = tasks_module.complete_task(task_id)
    assert completed["task"]["status"] == "done"
    assert tasks_module.list_tasks()["count"] == 0
    assert tasks_module.list_tasks(include_completed=True)["count"] == 1

    deleted = tasks_module.delete_task(task_id)
    assert deleted["status"] == "task_deleted"
    assert tasks_module.list_tasks(include_completed=True)["count"] == 0


def test_task_validation_errors(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    assert "error" in tasks_module.add_task("")
    created = tasks_module.add_task("Sponsor follow-up")
    task_id = created["task"]["task_id"]
    assert "error" in tasks_module.update_task(task_id, priority="urgent")
    assert "error" in tasks_module.update_task("missing", title="x")


class _FakeRequest:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        return self._payload


class _FakeTasklists:
    def list(self, **kwargs):
        return _FakeRequest({"items": [{"id": "L1", "title": "My Tasks"}]})


class _FakeRemoteTasks:
    def __init__(self):
        self.inserted = None
        self.patched = None
        self.deleted = None

    def list(self, **kwargs):
        return _FakeRequest({
            "items": [{
                "id": "g1",
                "title": "Remind sponsors",
                "notes": "Send deck",
                "status": "needsAction",
                "due": "2026-12-05T00:00:00.000Z",
            }]
        })

    def insert(self, **kwargs):
        self.inserted = kwargs
        return _FakeRequest({"id": "g2", **kwargs.get("body", {})})

    def patch(self, **kwargs):
        self.patched = kwargs
        return _FakeRequest({"id": kwargs.get("task")})

    def delete(self, **kwargs):
        self.deleted = kwargs
        return _FakeRequest({})


class _FakeService:
    def __init__(self):
        self._tasks = _FakeRemoteTasks()

    def tasklists(self):
        return _FakeTasklists()

    def tasks(self):
        return self._tasks


def test_sync_pulls_remote_and_pushes_local(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    service = _FakeService()
    monkeypatch.setattr(
        tasks_module.google_auth,
        "get_service",
        lambda api, version: service,
    )
    monkeypatch.setattr(tasks_module, "GOOGLE_TASKS_LIST_ID", "@default")

    created = tasks_module.add_task("Book auditorium", due="2026-12-02")
    local_id = created["task"]["task_id"]

    result = tasks_module.sync()
    assert result["status"] == "synced"
    assert result["pulled"] == 1
    assert result["pushed"] == 1

    all_tasks = tasks_module.list_tasks(include_completed=True)["tasks"]
    titles = {task["title"] for task in all_tasks}
    assert {"Book auditorium", "Remind sponsors"} <= titles

    local = next(t for t in all_tasks if t["task_id"] == local_id)
    assert local["google_task_id"] == "g2"
    assert service._tasks.inserted["tasklist"] == "L1"
    assert service._tasks.inserted["body"]["due"] == "2026-12-02T00:00:00.000Z"

    remote = next(t for t in all_tasks if t["google_task_id"] == "g1")
    assert remote["source"] == "google"
    assert remote["due"] == "2026-12-05"


def test_sync_surfaces_auth_errors(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    class _Denied(Exception):
        class resp:
            status = 403

    def _deny(api, version):
        raise _Denied("insufficient permissions")

    monkeypatch.setattr(tasks_module, "HttpError", _Denied)
    monkeypatch.setattr(tasks_module.google_auth, "get_service", _deny)
    result = tasks_module.sync()
    assert "error" in result
    assert result["needs_auth"] is True
