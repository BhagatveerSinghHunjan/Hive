"""Gmail write layer: drafts, sends, labels, header safety, tiers."""

import asyncio
import base64
import json
from email import message_from_string

from hive.integrations import gmail as gmail_module
from hive.integrations.gmail import _clean_header, _encode_raw
from hive.permissions import get_tool_tier, should_auto_allow
from hive.tools import TOOLS


class _FakeRequest:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        return self._payload


class _FakeDrafts:
    def __init__(self):
        self.last_body = None

    def create(self, userId, body):
        self.last_body = body
        return _FakeRequest({
            "id": "d1",
            "message": {"id": "m1", "threadId": body["message"].get("threadId", "t1")},
        })

    def send(self, userId, body):
        self.last_body = body
        return _FakeRequest({"id": "m2", "threadId": "t1", "labelIds": ["SENT"]})


class _FakeMessages:
    def __init__(self):
        self.last_body = None

    def send(self, userId, body):
        self.last_body = body
        return _FakeRequest({"id": "m3", "threadId": "t1", "labelIds": ["SENT"]})

    def modify(self, userId, id, body):
        self.last_body = body
        labels = ["SENT"]
        labels += [label for label in body.get("addLabelIds", []) if label not in labels]
        labels = [label for label in labels if label not in body.get("removeLabelIds", [])]
        return _FakeRequest({"id": id, "labelIds": labels})


class _FakeUsers:
    def __init__(self):
        self._drafts = _FakeDrafts()
        self._messages = _FakeMessages()

    def drafts(self):
        return self._drafts

    def messages(self):
        return self._messages


class _FakeService:
    def __init__(self):
        self._users = _FakeUsers()

    def users(self):
        return self._users


def _install(monkeypatch):
    service = _FakeService()
    monkeypatch.setattr(
        gmail_module.google_auth,
        "get_service",
        lambda api, version: service,
    )
    return service


def _decode_raw(raw: str) -> str:
    padded = raw + "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8")


def test_write_tools_registered_with_correct_tiers():
    expected = {
        "gmail_create_draft": "moderate",
        "gmail_send_draft": "sensitive",
        "gmail_send_message": "sensitive",
        "gmail_modify_labels": "moderate",
        "gmail_archive": "moderate",
        "gmail_mark_read": "moderate",
    }
    for name, tier in expected.items():
        assert name in TOOLS
        assert get_tool_tier(name) == tier


def test_outbound_sends_never_auto_allow():
    assert should_auto_allow("gmail_send_message", "") is False
    assert should_auto_allow("gmail_send_draft", "d1") is False
    assert should_auto_allow("browser_checkout", "{}") is False


def test_header_injection_is_stripped():
    assert _clean_header("Ananya\r\nBcc: evil@example.com") == "Ananya Bcc: evil@example.com"
    raw = _encode_raw("venue@example.com", "Subject\r\nBcc: evil@example.com", "Hi")
    decoded = _decode_raw(raw)
    assert "\r\nBcc: evil@example.com" not in decoded


def test_create_draft_encodes_message_and_thread(monkeypatch):
    _install(monkeypatch)
    result = gmail_module.create_draft(
        "venue@example.com",
        "Venue confirmation",
        "Can we confirm Friday?",
        thread_id="t1",
        in_reply_to="<m1@example.com>",
    )
    assert result["status"] == "draft_created"
    assert result["draft_id"] == "d1"
    assert result["thread_id"] == "t1"
    assert result["sent"] is False


def test_create_draft_message_round_trip(monkeypatch):
    service = _install(monkeypatch)
    gmail_module.create_draft(
        "venue@example.com",
        "Re: Venue",
        "Works for us.",
        cc="advisor@example.com",
        in_reply_to="<m1@example.com>",
    )
    raw = service.users().drafts().last_body["message"]["raw"]
    decoded = _decode_raw(raw)
    assert "To: venue@example.com" in decoded
    assert "Cc: advisor@example.com" in decoded
    assert "In-Reply-To: <m1@example.com>" in decoded
    assert "References: <m1@example.com>" in decoded

    message = message_from_string(decoded)
    body = message.get_payload(decode=True).decode("utf-8")
    assert "Works for us." in body


def test_send_draft_and_send_message(monkeypatch):
    _install(monkeypatch)
    draft = gmail_module.send_draft("d1")
    assert draft["status"] == "sent"
    assert draft["draft_id"] == "d1"

    sent = gmail_module.send_message("sponsor@example.com", "Thanks", "Appreciate it.")
    assert sent["status"] == "sent"
    assert sent["to"] == "sponsor@example.com"


def test_modify_labels_archive_and_mark_read(monkeypatch):
    _install(monkeypatch)
    modified = gmail_module.modify_labels("m1", add_labels="STARRED", remove_labels="INBOX")
    assert modified["status"] == "labels_updated"
    assert "STARRED" in modified["label_ids"]

    archived = gmail_module.archive_message("m1")
    assert archived["status"] == "archived"

    read = gmail_module.mark_read("m1")
    assert read["status"] == "read"
    unread = gmail_module.mark_read("m1", read=False)
    assert unread["status"] == "unread"


def test_write_tool_dispatch_through_registry(monkeypatch):
    from hive.integrations.registry import run_integration_tool

    _install(monkeypatch)
    result = asyncio.run(
        run_integration_tool(
            "gmail_create_draft",
            to="venue@example.com",
            subject="Venue",
            body="Confirming Friday.",
        )
    )
    assert result["status"] == "draft_created"
    assert "access_token" not in json.dumps(result).lower()
