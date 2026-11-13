"""Google OAuth 2.0 manager for Gmail and Calendar.

Credentials never leave this module. Tool handlers receive API clients, not
tokens, and tool results only contain mailbox data.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from hive.config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_OAUTH_CLIENT_FILE,
    GOOGLE_OAUTH_SCOPES,
    GOOGLE_TOKEN_FILE,
    HIVE_HOME,
    HIVE_TIMEZONE,
)

logger = logging.getLogger(__name__)

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    GOOGLE_LIBS_AVAILABLE = True
except Exception:  # pragma: no cover - depends on optional runtime packages
    Request = None
    Credentials = None
    InstalledAppFlow = None
    build = None
    GOOGLE_LIBS_AVAILABLE = False


INSTALL_HINT = (
    "Google libraries are not installed. Run: "
    "py -3.13 -m pip install google-api-python-client google-auth "
    "google-auth-oauthlib google-auth-httplib2"
)


class GoogleIntegrationError(RuntimeError):
    """Base error for Google integration problems."""


class GoogleNotConfigured(GoogleIntegrationError):
    """No OAuth client configuration is available."""


class GoogleNotConnected(GoogleIntegrationError):
    """No usable user token is available."""


class GoogleAuthManager:
    """Own the Google OAuth client, token, and API service construction."""

    def __init__(self) -> None:
        self.token_path = Path(GOOGLE_TOKEN_FILE).expanduser()

    def _client_config(self) -> tuple[dict, str]:
        """Return (client_config, source) for InstalledAppFlow."""
        if not GOOGLE_LIBS_AVAILABLE:
            raise GoogleNotConfigured(INSTALL_HINT)

        if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
            return (
                {
                    "installed": {
                        "client_id": GOOGLE_CLIENT_ID,
                        "client_secret": GOOGLE_CLIENT_SECRET,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": ["http://localhost"],
                    }
                },
                "environment",
            )

        candidates: list[Path] = []
        if GOOGLE_OAUTH_CLIENT_FILE:
            candidates.append(Path(GOOGLE_OAUTH_CLIENT_FILE).expanduser())
        candidates.append(Path(HIVE_HOME).expanduser() / "google_oauth_client.json")

        for path in candidates:
            if not path.exists():
                continue
            try:
                config = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                raise GoogleNotConfigured(
                    f"Could not read Google OAuth client file {path}: {exc}"
                ) from exc
            if not isinstance(config, dict) or not (
                "installed" in config or "web" in config
            ):
                raise GoogleNotConfigured(
                    f"{path} is not a Google OAuth client JSON file."
                )
            return config, str(path)

        raise GoogleNotConfigured(
            "Google OAuth is not configured. Download a Desktop OAuth client "
            "JSON from Google Cloud and save it to "
            f"{Path(HIVE_HOME) / 'google_oauth_client.json'}, or set "
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env."
        )

    def load_credentials(self, refresh: bool = True):
        """Load and, when needed, refresh the stored user token."""
        if not GOOGLE_LIBS_AVAILABLE:
            raise GoogleNotConfigured(INSTALL_HINT)
        if not self.token_path.exists():
            return None

        try:
            creds = Credentials.from_authorized_user_file(
                str(self.token_path), scopes=GOOGLE_OAUTH_SCOPES
            )
        except Exception as exc:
            raise GoogleNotConnected(
                f"Stored Google token is unreadable: {exc}. Reconnect Google."
            ) from exc

        if creds.expired and creds.refresh_token and refresh:
            try:
                creds.refresh(Request())
            except Exception as exc:
                raise GoogleNotConnected(
                    f"Google token refresh failed: {exc}. Reconnect Google."
                ) from exc
            self._save_token(creds)

        if not creds.valid:
            raise GoogleNotConnected(
                "Stored Google token is invalid or expired. Reconnect Google."
            )
        return creds

    def _save_token(self, creds) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.token_path.with_suffix(".json.tmp")
        tmp.write_text(creds.to_json(), encoding="utf-8")
        tmp.replace(self.token_path)
        try:
            os.chmod(self.token_path, 0o600)
        except OSError:
            pass

    def connect(self, port: int | None = None, open_browser: bool = True) -> dict:
        """Run the installed-app OAuth flow and persist the token.

        This is blocking by design. Call it with ``asyncio.to_thread`` from an
        async server so the event loop and desktop bridge stay responsive.
        """
        if not GOOGLE_LIBS_AVAILABLE:
            raise GoogleNotConfigured(INSTALL_HINT)

        # Google may still expand or reorder scopes in the token response.
        # oauthlib raises a Warning exception for that, which would throw away
        # a perfectly valid consent; log it instead.
        os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

        client_config, _source = self._client_config()
        flow = InstalledAppFlow.from_client_config(
            client_config, scopes=GOOGLE_OAUTH_SCOPES
        )
        if port is None:
            port = int(os.environ.get("GOOGLE_OAUTH_PORT", "0"))
        creds = flow.run_local_server(
            port=port,
            access_type="offline",
            prompt="consent",
            open_browser=open_browser,
        )
        self._save_token(creds)
        return self.status(verify=True)

    def disconnect(self) -> bool:
        """Delete the stored token. The client config is left untouched."""
        if self.token_path.exists():
            self.token_path.unlink()
            return True
        return False

    def get_service(self, api: str, version: str):
        """Build an authenticated Google API service."""
        creds = self.load_credentials()
        if creds is None:
            raise GoogleNotConnected(
                "Google is not connected. Run: py -m hive.cli --connect-google"
            )
        return build(api, version, credentials=creds, cache_discovery=False)

    def gmail_profile(self) -> dict:
        """Return the authenticated Gmail account summary."""
        service = self.get_service("gmail", "v1")
        profile = service.users().getProfile(userId="me").execute()
        return {
            "email": profile.get("emailAddress"),
            "messages_total": profile.get("messagesTotal"),
            "threads_total": profile.get("threadsTotal"),
            "history_id": profile.get("historyId"),
        }

    def status(self, verify: bool = False) -> dict:
        """Return a credential-safe status object for CLI/UI display."""
        info = {
            "libraries_installed": GOOGLE_LIBS_AVAILABLE,
            "client_configured": False,
            "client_source": None,
            "token_present": self.token_path.exists(),
            "connected": False,
            "email": None,
            "scopes": list(GOOGLE_OAUTH_SCOPES),
            "timezone": HIVE_TIMEZONE,
            "error": None,
        }

        try:
            _config, source = self._client_config()
            info["client_configured"] = True
            info["client_source"] = source
        except GoogleNotConfigured as exc:
            config_error = str(exc)
        else:
            config_error = None

        try:
            creds = self.load_credentials()
        except GoogleNotConnected as exc:
            info["error"] = str(exc)
            return info

        if creds is None:
            info["error"] = config_error or "Google account is not connected yet."
            return info

        info["connected"] = True
        info["scopes"] = list(creds.scopes or GOOGLE_OAUTH_SCOPES)

        if verify:
            try:
                profile = self.gmail_profile()
                info["email"] = profile.get("email")
                info["messages_total"] = profile.get("messages_total")
                info["threads_total"] = profile.get("threads_total")
            except Exception as exc:
                info["connected"] = False
                info["error"] = f"Gmail verification failed: {exc}"

        return info


google_auth = GoogleAuthManager()
