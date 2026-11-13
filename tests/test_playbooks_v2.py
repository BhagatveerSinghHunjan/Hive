"""Playbook schema v2, recorder, and replay tests."""

import asyncio

import pytest

from hive import playbooks
from hive.permissions import get_tool_tier
from hive.tools import TOOLS


@pytest.fixture(autouse=True)
def _isolate_playbooks(monkeypatch, tmp_path):
    monkeypatch.setattr(playbooks, "PLAYBOOK_DIR", tmp_path / "playbooks")
    yield


def test_playbook_tools_registered():
    expected = {
        "browser_record_start": "moderate",
        "browser_record_stop": "moderate",
        "browser_playbook_list": "safe",
        "browser_playbook_show": "safe",
        "browser_playbook_replay": "moderate",
        "browser_playbook_forget": "moderate",
    }
    for name, tier in expected.items():
        assert name in TOOLS
        assert get_tool_tier(name) == tier


def test_save_and_get_flow():
    playbooks.save_flow("example.com", "login", [
        {"action": "goto", "url": "https://example.com/login"},
        {"action": "type", "selector": "#email", "text": "${email}"},
        {"action": "click", "selector": "button[type=submit]"},
        {"action": "bogus"},
    ])
    flow = playbooks.get_flow("https://example.com/login", "login")
    assert flow is not None
    assert len(flow["steps"]) == 3
    assert flow["steps"][1]["text"] == "${email}"

    listing = playbooks.list_flows("example.com")
    assert listing["flows"]["login"]["steps"] == 3
    assert playbooks.load_playbook("example.com")["schema_version"] == 2


def test_trust_level_mapping_and_updates():
    assert playbooks.trust_level_for_score(0) == 0
    assert playbooks.trust_level_for_score(30) == 1
    assert playbooks.trust_level_for_score(60) == 2
    assert playbooks.trust_level_for_score(85) == 3

    pb = playbooks.record_success("example.com", flow="login", trust_delta=70)
    assert pb["trust_level"] == 2
    pb = playbooks.record_success("example.com", flow="login", trust_delta=20)
    assert pb["trust_level"] == 3
    pb = playbooks.record_failure("example.com", flow="login", trust_delta=-50)
    assert pb["trust_level"] <= 1


def test_delete_flow_and_playbook():
    playbooks.save_flow("example.com", "login", [{"action": "goto", "url": "https://x"}])
    playbooks.save_flow("example.com", "signup", [{"action": "goto", "url": "https://y"}])
    assert playbooks.delete_flow("example.com", "login") is True
    listing = playbooks.list_flows("example.com")
    assert "login" not in listing["flows"]
    assert playbooks.delete_playbook("example.com") is True
    assert playbooks.list_playbooks()["count"] == 0


class _FakeKeyboard:
    def __init__(self):
        self.pressed = []

    async def press(self, key):
        self.pressed.append(key)


class _FakePage:
    def __init__(self):
        self.url = "about:blank"
        self.actions = []
        self.keyboard = _FakeKeyboard()

    async def goto(self, url, **kwargs):
        self.url = url
        self.actions.append(("goto", url))

    async def click(self, selector, **kwargs):
        self.actions.append(("click", selector))

    async def fill(self, selector, text, **kwargs):
        self.actions.append(("fill", selector, text))

    async def press(self, selector, key, **kwargs):
        self.actions.append(("press", selector, key))

    async def wait_for_load_state(self, *args, **kwargs):
        return None

    async def wait_for_timeout(self, ms):
        return None


class _FakePool:
    def __init__(self, page):
        self.page = page

    async def get_page(self, session_id=None):
        return self.page


def test_replay_flow_substitutes_sensitive_data(monkeypatch):
    playbooks.save_flow("example.com", "login", [
        {"action": "goto", "url": "https://example.com/login"},
        {"action": "type", "selector": "#email", "text": "${email}"},
        {"action": "type", "selector": "#password", "text": "${password}"},
        {"action": "click", "selector": "button[type=submit]"},
    ])

    page = _FakePage()
    from hive.browser import replay as replay_module

    result = asyncio.run(replay_module.replay_flow(
        "example.com", "login",
        sensitive_data={"email": "ananya@example.com", "password": "secret"},
        page=page,
    ))
    assert result["status"] == "replayed"
    assert result["steps_executed"] == 4
    assert ("fill", "#email", "ananya@example.com") in page.actions
    assert "secret" not in str(result)


def test_replay_reports_missing_sensitive_keys(monkeypatch):
    playbooks.save_flow("example.com", "login", [
        {"action": "type", "selector": "#email", "text": "${email}"},
    ])
    page = _FakePage()
    from hive.browser import replay as replay_module

    result = asyncio.run(replay_module.replay_flow("example.com", "login", page=page))
    assert result["status"] == "failed"
    assert result["missing_sensitive_keys"] == ["email"]


def test_recorder_saves_flow():
    from hive.browser.recorder import BrowserRecorder

    recorder = BrowserRecorder()
    started = recorder.start("login", site="https://example.com/login")
    assert started["status"] == "recording"
    recorder.record_goto("https://example.com/login")
    recorder.record_type("#email", "${email}", press_enter=True)
    recorder.record_click("button[type=submit]")
    saved = recorder.stop(save=True)

    assert saved["status"] == "saved"
    flow = playbooks.get_flow("example.com", "login")
    assert flow is not None
    actions = [step["action"] for step in flow["steps"]]
    assert actions == ["goto", "type", "press", "click"]
    assert playbooks.load_playbook("example.com")["flows"]["login"]["steps"][1]["text"] == "${email}"
