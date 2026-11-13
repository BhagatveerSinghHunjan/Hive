"""Trust ladder, personas, and CAPTCHA fallback tests."""

import asyncio

import pytest

from hive import personas, trust
from hive.permissions import should_auto_allow


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(trust, "TRUST_FILE", tmp_path / "trust.json")
    monkeypatch.setattr(personas, "HIVE_PERSONA_FILE", tmp_path / "personas.json")
    yield


def test_trust_levels_list_set_and_permissions():
    assert trust.set_level("https://Example.com/login", 2)["level"] == 2
    assert trust.get_level("example.com") == 2
    assert trust.has_explicit_level("example.com") is True

    listing = trust.list_levels()
    assert listing["domains"][0]["domain"] == "example.com"

    assert should_auto_allow("browser_open", "https://example.com") is True
    assert should_auto_allow("browser_click", "https://example.com") is False

    trust.set_level("example.com", 0)
    assert should_auto_allow("browser_open", "https://example.com") is False


def test_trust_never_allows_outbound():
    trust.set_level("example.com", 3)
    assert should_auto_allow("browser_checkout", "https://example.com") is False
    assert should_auto_allow("gmail_send_message", "") is False
    assert trust.can_auto_allow("calendar_create_event", "example.com") is False


def test_approval_target_includes_playbook_site():
    from hive.runtime import format_approval_target

    target = format_approval_target(
        "browser_playbook_replay",
        {"site": "example.com", "flow": "login"},
    )
    assert "example.com" in target
    assert "login" in target
    assert "github.com" in format_approval_target("browser_open", {"url": "https://github.com/x"})


def test_trust_rejects_invalid_level():
    assert "error" in trust.set_level("example.com", 9)
    assert trust.TRUST_FILE.exists() is False


def test_persona_create_list_and_use(monkeypatch):
    created = personas.create_persona("work", "Work twin", max_order_amount=50)
    assert created["status"] == "created"

    duplicate = personas.create_persona("work")
    assert "error" in duplicate

    listing = personas.list_personas()
    assert listing["active"] == "default"
    assert any(p["name"] == "work" for p in listing["personas"])

    monkeypatch.setattr(personas, "apply_persona", lambda name: {"applied": True})
    used = personas.use_persona("work")
    assert used["status"] == "active"
    assert personas.active_persona()["name"] == "work"

    missing = personas.use_persona("nope")
    assert "error" in missing


def test_persona_name_validation():
    assert "error" in personas.create_persona("")
    assert "error" in personas.create_persona("bad name!")


def test_captcha_detection_and_human_fallback(monkeypatch):
    from hive.browser import captcha

    assert captcha.detect_from_elements([{"text": "I'm not a robot"}]) is True
    assert captcha.detect_from_elements([{"text": "Email"}]) is False

    async def _handoff(site, url=""):
        return True

    monkeypatch.setattr(captcha, "HIVE_CAPTCHA_PROVIDER", "human")
    monkeypatch.setattr("hive.interactive.prompt_captcha_handoff", _handoff)
    result = asyncio.run(captcha.handle_captcha("example.com", "https://example.com"))
    assert result["status"] == "solved"
    assert result["provider"] == "human"
    assert result["requires_human"] is False


def test_captcha_declined_handoff(monkeypatch):
    from hive.browser import captcha

    async def _handoff(site, url=""):
        return False

    monkeypatch.setattr(captcha, "HIVE_CAPTCHA_PROVIDER", "human")
    monkeypatch.setattr("hive.interactive.prompt_captcha_handoff", _handoff)
    result = asyncio.run(captcha.handle_captcha("example.com"))
    assert result["status"] == "captcha_required"
    assert result["requires_human"] is True
