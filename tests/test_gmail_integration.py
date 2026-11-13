"""Gmail integration parsing, registration, and failure-path tests."""

import asyncio
import base64
import json

from hive.integrations.gmail import (
    _api_error,
    _decode_header,
    _extract_body,
    _message,
)
from hive.integrations.registry import integration_status, run_integration_tool
from hive.permissions import get_tool_tier
from hive.tools import TOOLS


def _b64(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def test_gmail_tools_registered_and_read_only():
    expected = {"gmail_status", "gmail_search", "gmail_read_thread", "gmail_list_labels"}
    assert expected <= set(TOOLS)
    for name in expected:
        assert get_tool_tier(name) == "safe"


def test_tool_schema_marks_required_arguments():
    from hive.llm import QwenClient

    schema = QwenClient(api_key="test").build_tools_schema(TOOLS)
    required = {
        item["function"]["name"]: item["function"]["parameters"]["required"]
        for item in schema
    }
    assert required["gmail_search"] == ["query"]
    assert required["gmail_read_thread"] == ["thread_id"]
    assert required["gmail_status"] == []
    # Existing heuristic must stay intact for old tools.
    assert required["read_file"] == ["path"]


def test_decode_rfc2047_header():
    encoded = "=?UTF-8?B?QW5hbnlh?="
    assert _decode_header(encoded) == "Ananya"


def test_extract_plain_text_body():
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": _b64("Hello team")}},
        ],
    }
    text, content_type = _extract_body(payload)
    assert text == "Hello team"
    assert content_type == "text/plain"


def test_extract_html_fallback_skips_script_content():
    html = (
        "<html><body><p>Hello <b>team</b></p>"
        "<script>bad()</script></body></html>"
    )
    payload = {"mimeType": "text/html", "body": {"data": _b64(html)}}
    text, content_type = _extract_body(payload)
    assert "Hello team" in text
    assert "bad()" not in text
    assert content_type == "text/html"


def test_message_summary_and_attachment_metadata():
    message = {
        "id": "m1",
        "threadId": "t1",
        "labelIds": ["UNREAD", "INBOX"],
        "snippet": "Short preview",
        "internalDate": "1700000000000",
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "From", "value": "Ananya <ananya@example.com>"},
                {"name": "Subject", "value": "Venue confirmation"},
            ],
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _b64("Body text")}},
                {
                    "mimeType": "application/pdf",
                    "filename": "quote.pdf",
                    "body": {"attachmentId": "att1", "size": 1234},
                },
            ],
        },
    }
    result = _message(message, 6000)
    assert result["unread"] is True
    assert result["from"] == "Ananya <ananya@example.com>"
    assert result["subject"] == "Venue confirmation"
    assert result["body"] == "Body text"
    assert result["attachments"][0]["filename"] == "quote.pdf"
    assert result["untrusted"] is True


def test_api_error_flags_authentication_failure():
    class FakeResponse:
        status = 401

    class FakeError(Exception):
        resp = FakeResponse()

    result = _api_error(FakeError("unauthorized"))
    assert result["needs_auth"] is True
    assert result["status_code"] == 401


def _contains_key(value, key):
    if isinstance(value, dict):
        return key in value or any(_contains_key(v, key) for v in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


def test_integration_status_never_exposes_credentials(monkeypatch, tmp_path):
    from hive.integrations.google_auth import google_auth

    monkeypatch.setattr(google_auth, "token_path", tmp_path / "google_token.json")
    status = asyncio.run(integration_status(verify=False))
    for secret_key in ("access_token", "refresh_token", "client_secret", "id_token"):
        assert not _contains_key(status, secret_key)
    assert "google" in status
    assert "slack" in status


def test_error_redaction_removes_token_fragments():
    from hive.integrations.registry import _redact

    text = "request failed: access_token=ya29.secret refresh_token: 1//abc"
    redacted = _redact(text)
    assert "ya29.secret" not in redacted
    assert "1//abc" not in redacted
    assert "[REDACTED]" in redacted


def test_google_scopes_use_canonical_userinfo_urls():
    """Google expands the email/profile aliases, which oauthlib rejects."""
    from hive.config import GOOGLE_OAUTH_SCOPES

    assert "https://www.googleapis.com/auth/userinfo.email" in GOOGLE_OAUTH_SCOPES
    assert "https://www.googleapis.com/auth/userinfo.profile" in GOOGLE_OAUTH_SCOPES
    assert "email" not in GOOGLE_OAUTH_SCOPES
    assert "profile" not in GOOGLE_OAUTH_SCOPES


def test_gmail_tool_returns_actionable_setup_error_when_disconnected(
    monkeypatch, tmp_path
):
    from hive.integrations.google_auth import google_auth

    monkeypatch.setattr(google_auth, "token_path", tmp_path / "google_token.json")
    result = asyncio.run(run_integration_tool("gmail_search", query="is:unread"))
    assert "error" in result
    assert result.get("needs_auth") or result.get("needs_setup")
    # Must not raise or return a raw token representation.
    assert "access_token" not in json.dumps(result).lower()


class _FakeRequest:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        return self._payload


def _metadata_message():
    return {
        "id": "m1",
        "threadId": "t1",
        "labelIds": ["UNREAD", "INBOX"],
        "snippet": "Can we confirm the venue?",
        "internalDate": "1700000000000",
        "payload": {
            "headers": [
                {"name": "From", "value": "Venue <venue@example.com>"},
                {"name": "Subject", "value": "Venue confirmation"},
                {"name": "Date", "value": "Tue, 14 Nov 2026 10:00:00 +0530"},
            ]
        },
    }


def _full_thread():
    return {
        "id": "t1",
        "messages": [
            {
                **_metadata_message(),
                "payload": {
                    "mimeType": "text/plain",
                    "headers": _metadata_message()["payload"]["headers"],
                    "body": {"data": _b64("The auditorium is available on Friday.")},
                },
            }
        ],
    }


class _FakeMessages:
    def list(self, **_kwargs):
        return _FakeRequest({"messages": [{"id": "m1", "threadId": "t1"}]})

    def get(self, **kwargs):
        if kwargs.get("format") == "metadata":
            return _FakeRequest(_metadata_message())
        return _FakeRequest(_metadata_message())


class _FakeThreads:
    def get(self, **_kwargs):
        return _FakeRequest(_full_thread())


class _FakeUsers:
    def messages(self):
        return _FakeMessages()

    def threads(self):
        return _FakeThreads()


class _FakeGmailService:
    def users(self):
        return _FakeUsers()


def test_search_messages_shapes_real_api_response(monkeypatch):
    from hive.integrations import gmail as gmail_module

    monkeypatch.setattr(
        gmail_module.google_auth,
        "get_service",
        lambda api, version: _FakeGmailService(),
    )
    result = gmail_module.search_messages("is:unread", 5)
    assert result["count"] == 1
    assert result["query"] == "is:unread"
    assert result["messages"][0]["message_id"] == "m1"
    assert result["messages"][0]["thread_id"] == "t1"
    assert result["messages"][0]["subject"] == "Venue confirmation"
    assert result["messages"][0]["unread"] is True


def test_read_thread_decodes_body(monkeypatch):
    from hive.integrations import gmail as gmail_module

    monkeypatch.setattr(
        gmail_module.google_auth,
        "get_service",
        lambda api, version: _FakeGmailService(),
    )
    result = gmail_module.read_thread("t1", 6000)
    assert result["thread_id"] == "t1"
    assert result["subject"] == "Venue confirmation"
    assert result["count"] == 1
    assert "auditorium is available" in result["messages"][0]["body"]
    assert result["messages"][0]["untrusted"] is True


def test_execute_tool_dispatches_gmail_integration(monkeypatch):
    from hive.integrations import gmail as gmail_module
    from hive.tools import execute_tool

    monkeypatch.setattr(
        gmail_module.google_auth,
        "get_service",
        lambda api, version: _FakeGmailService(),
    )
    result = asyncio.run(
        execute_tool("gmail_search", query="is:unread", max_results=5)
    )
    assert result["count"] == 1
    assert result["messages"][0]["subject"] == "Venue confirmation"
    assert "duration_ms" in result


