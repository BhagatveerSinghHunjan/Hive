"""Spotify Web API control — OAuth + playback (no Chrome).

Requires a Spotify Developer app + Premium for playback:
  https://developer.spotify.com/dashboard

Env:
  SPOTIFY_CLIENT_ID
  SPOTIFY_CLIENT_SECRET
  SPOTIFY_REDIRECT_URI   (default http://127.0.0.1:8899/callback)
  SPOTIFY_TOKEN_FILE     (default ~/.hive/spotify_token.json)
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import secrets
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import httpx

from hive.config import HIVE_HOME

logger = logging.getLogger(__name__)

API = "https://api.spotify.com/v1"
AUTH = "https://accounts.spotify.com"
SCOPES = " ".join(
    [
        "user-read-playback-state",
        "user-modify-playback-state",
        "user-read-currently-playing",
        "user-read-email",
        "user-read-private",
    ]
)


class SpotifyError(RuntimeError):
    pass


class SpotifyNotConfigured(SpotifyError):
    pass


class SpotifyNotConnected(SpotifyError):
    pass


def _env(name: str, default: str = "") -> str:
    import os

    return (os.environ.get(name) or default).strip()


def _client_id() -> str:
    return _env("SPOTIFY_CLIENT_ID")


def _client_secret() -> str:
    return _env("SPOTIFY_CLIENT_SECRET")


def _redirect_uri() -> str:
    return _env("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8899/callback")


def _token_path() -> Path:
    custom = _env("SPOTIFY_TOKEN_FILE")
    if custom:
        return Path(custom).expanduser()
    return Path(HIVE_HOME).expanduser() / "spotify_token.json"


def configured() -> bool:
    return bool(_client_id() and _client_secret())


def connected() -> bool:
    return _token_path().exists()


def _load_token() -> dict:
    path = _token_path()
    if not path.exists():
        raise SpotifyNotConnected(
            "Spotify is not connected. Run: python -m hive.cli --connect-spotify"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _save_token(data: dict) -> None:
    path = _token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _basic_auth_header() -> str:
    raw = f"{_client_id()}:{_client_secret()}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def _refresh_token(refresh: str) -> dict:
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{AUTH}/api/token",
            headers={
                "Authorization": _basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh,
            },
        )
    if resp.status_code >= 400:
        raise SpotifyNotConnected(f"Spotify token refresh failed: {resp.text[:300]}")
    data = resp.json()
    stored = _load_token()
    stored["access_token"] = data["access_token"]
    stored["expires_at"] = int(time.time()) + int(data.get("expires_in", 3600)) - 60
    if data.get("refresh_token"):
        stored["refresh_token"] = data["refresh_token"]
    _save_token(stored)
    return stored


def _access_token() -> str:
    if not configured():
        raise SpotifyNotConfigured(
            "Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env "
            "(https://developer.spotify.com/dashboard)."
        )
    token = _load_token()
    if int(token.get("expires_at") or 0) <= int(time.time()):
        token = _refresh_token(token["refresh_token"])
    return token["access_token"]


def _parse_api_response(resp: httpx.Response) -> Any:
    """Spotify sometimes returns 204, empty bodies, or opaque non-JSON 200s (queue/next)."""
    if resp.status_code == 204 or not resp.content:
        return {"ok": True}
    text = resp.text.strip()
    if not text:
        return {"ok": True}
    try:
        return resp.json()
    except json.JSONDecodeError:
        # queue / next often return a bare token string with 200
        return {"ok": True, "raw": text[:120]}


async def _api(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
) -> Any:
    token = _access_token()
    url = f"{API}{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(
            method,
            url,
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            json=json_body,
        )
    if resp.status_code == 401:
        token_data = _refresh_token(_load_token()["refresh_token"])
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(
                method,
                url,
                headers={"Authorization": f"Bearer {token_data['access_token']}"},
                params=params,
                json=json_body,
            )
    if resp.status_code >= 400:
        detail = resp.text[:400]
        if resp.status_code == 404 and "device" in detail.lower():
            return {
                "error": (
                    "No active Spotify device. Open Spotify on your phone/desktop "
                    "(Premium), play anything once, then retry."
                ),
                "status": 404,
            }
        return {"error": f"Spotify API {resp.status_code}: {detail}", "status": resp.status_code}
    return _parse_api_response(resp)


def connect_spotify() -> dict:
    """Run localhost OAuth and store tokens. Blocking."""
    if not configured():
        raise SpotifyNotConfigured(
            "Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env first."
        )

    state = secrets.token_urlsafe(16)
    redirect = _redirect_uri()
    parsed = urllib.parse.urlparse(redirect)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8899
    result: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if qs.get("state", [""])[0] != state:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Invalid state")
                return
            if "error" in qs:
                result["error"] = qs["error"][0]
            else:
                result["code"] = qs.get("code", [""])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Spotify connected. You can close this tab.")

        def log_message(self, format, *args):  # noqa: A003
            return

    auth_url = (
        f"{AUTH}/authorize?"
        + urllib.parse.urlencode(
            {
                "client_id": _client_id(),
                "response_type": "code",
                "redirect_uri": redirect,
                "scope": SCOPES,
                "state": state,
                "show_dialog": "true",
            }
        )
    )
    server = HTTPServer((host, port), Handler)
    print(f"Opening Spotify login…\nIf the browser does not open, visit:\n{auth_url}\n")
    webbrowser.open(auth_url)
    while "code" not in result and "error" not in result:
        server.handle_request()
    server.server_close()

    if result.get("error"):
        raise SpotifyError(result["error"])
    code = result.get("code")
    if not code:
        raise SpotifyError("No authorization code returned.")

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{AUTH}/api/token",
            headers={
                "Authorization": _basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect,
            },
        )
    if resp.status_code >= 400:
        raise SpotifyError(f"Token exchange failed: {resp.text[:400]}")
    data = resp.json()
    _save_token(
        {
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "expires_at": int(time.time()) + int(data.get("expires_in", 3600)) - 60,
            "scope": data.get("scope", SCOPES),
            "token_type": data.get("token_type", "Bearer"),
        }
    )
    return {"ok": True, "token_file": str(_token_path())}


def disconnect_spotify() -> dict:
    path = _token_path()
    if path.exists():
        path.unlink()
    return {"ok": True, "disconnected": True}


def _rank_tracks(query: str, tracks: list[dict]) -> list[dict]:
    """Prefer artist + title matches (avoid cover/extended spam for named artists)."""
    q = (query or "").lower().strip()
    if not q or not tracks:
        return tracks
    tokens = [p for p in q.split() if len(p) > 1]

    def score(track: dict) -> tuple:
        name = (track.get("name") or "").lower()
        artists = (track.get("artists") or "").lower()
        artist_hits = sum(1 for p in tokens if len(p) > 2 and p in artists)
        title_tokens = [p for p in tokens if p not in artists] or tokens
        title_q = " ".join(title_tokens).strip() or q
        bare = name.split(" - ")[0].strip()
        exact = 1 if bare == title_q or name == title_q or bare == q else 0
        starts = 1 if bare.startswith(title_q) or title_q.startswith(bare) else 0
        contains = 1 if title_q in name or bare in title_q else 0
        # Penalize remix/cover/extended when the user didn't ask for them
        junk = ("extended", "remix", "cover", "karaoke", "sped up", "slowed")
        penalty = 1 if any(j in name for j in junk) and not any(j in q for j in junk) else 0
        return (artist_hits, exact, starts, contains, -penalty)

    return sorted(tracks, key=score, reverse=True)


async def search(query: str, search_type: str = "track,playlist", limit: int = 5) -> dict:
    data = await _api(
        "GET",
        "/search",
        params={"q": query, "type": search_type, "limit": min(max(limit, 5), 20)},
    )
    if isinstance(data, dict) and data.get("error"):
        return data
    tracks = []
    for item in (data.get("tracks") or {}).get("items") or []:
        tracks.append(
            {
                "id": item.get("id"),
                "uri": item.get("uri"),
                "name": item.get("name"),
                "artists": ", ".join(a.get("name", "") for a in item.get("artists") or []),
            }
        )
    tracks = _rank_tracks(query, tracks)[:limit]
    playlists = []
    for item in (data.get("playlists") or {}).get("items") or []:
        if not item:
            continue
        playlists.append(
            {
                "id": item.get("id"),
                "uri": item.get("uri"),
                "name": item.get("name"),
            }
        )
    return {"ok": True, "tracks": tracks, "playlists": playlists[:limit]}


async def whoami() -> dict:
    data = await _api("GET", "/me")
    if isinstance(data, dict) and data.get("error"):
        return data
    return {
        "ok": True,
        "display_name": data.get("display_name"),
        "email": data.get("email"),
        "product": data.get("product"),
        "id": data.get("id"),
    }


async def list_devices() -> dict:
    data = await _api("GET", "/me/player/devices")
    if isinstance(data, dict) and data.get("error"):
        return data
    devices = data.get("devices") or []
    return {"ok": True, "devices": devices, "count": len(devices)}


async def _no_device_error() -> dict:
    me = await whoami()
    name = me.get("display_name") or "unknown"
    email = me.get("email") or "unknown"
    product = me.get("product") or "unknown"
    return {
        "error": (
            "Spotify API sees no Connect devices for this account. "
            f"Connected as {name} ({email}), plan={product}. "
            "1) In the Spotify desktop/phone app, log into THIS same account. "
            "2) Turn off Private session. "
            "3) Press play on any song so the device appears. "
            "4) Retry. Premium is required for remote play."
        ),
        "account": {"display_name": name, "email": email, "product": product},
    }


async def ensure_device(*, force_transfer: bool = False, resume: bool = False) -> dict:
    """Pick Lokesh's available device; transfer only if nothing is active.

    resume=False on transfer pauses playback — never use that right before a song change.
    """
    listed = await list_devices()
    if listed.get("error"):
        return listed
    devices = listed.get("devices") or []
    if not devices:
        return await _no_device_error()

    active = next((d for d in devices if d.get("is_active")), None)
    computers = [
        d for d in devices if (d.get("type") or "").lower() == "computer"
    ]
    preferred = active or (computers[0] if computers else devices[0])
    device_id = preferred.get("id")
    # Only transfer when needed. Transferring with play=False pauses the current track.
    if device_id and (force_transfer or not preferred.get("is_active")):
        transfer = await _api(
            "PUT",
            "/me/player",
            json_body={"device_ids": [device_id], "play": bool(resume)},
        )
        if isinstance(transfer, dict) and transfer.get("error"):
            logger.warning("spotify transfer failed: %s", transfer.get("error"))
        else:
            preferred = {**preferred, "is_active": True}
            if not resume:
                await asyncio.sleep(0.4)
    return {"ok": True, "device": preferred}


async def now_playing() -> dict:
    data = await _api("GET", "/me/player")
    if isinstance(data, dict) and data.get("error"):
        return data
    if not data or data is True or data.get("ok") is True and "item" not in data:
        # Distinguish empty player from our 204 stub.
        if not data or (isinstance(data, dict) and set(data.keys()) <= {"ok"}):
            return {"ok": True, "playing": False, "message": "Nothing is playing on the API player."}
    item = data.get("item") or {}
    artists = ", ".join(a.get("name", "") for a in item.get("artists") or [])
    return {
        "ok": True,
        "playing": bool(data.get("is_playing")),
        "name": item.get("name"),
        "artists": artists,
        "uri": item.get("uri"),
        "device": (data.get("device") or {}).get("name"),
    }


async def _queue_and_skip(uri: str, device: dict) -> dict | None:
    """Desktop Spotify often ignores PUT /play for track changes; queue+next works."""
    queued = await _api("POST", "/me/player/queue", params={"uri": uri})
    if isinstance(queued, dict) and queued.get("error"):
        return None
    skipped = await _api("POST", "/me/player/next")
    if isinstance(skipped, dict) and skipped.get("error"):
        return None
    await asyncio.sleep(0.7)
    verify = await now_playing()
    if verify.get("uri") == uri or (verify.get("playing") and verify.get("name")):
        return {"ok": True, "device": device, "via": "queue_next", "playing_now": verify}
    return None


async def _play_body(body: dict) -> dict:
    ready = await ensure_device()
    if ready.get("error"):
        return ready
    device = ready.get("device") or {}
    device_id = device.get("id")
    params = {"device_id": device_id} if device_id else None
    # Never send an empty JSON object — Spotify treats {} as "resume", not a new track.
    json_body = body if body else None
    uris = list((body or {}).get("uris") or []) if body else []

    # While something is already playing, /play with uris often returns 204 and does nothing.
    # Queue the track and skip — that actually switches songs on desktop Connect.
    if len(uris) == 1:
        current = await now_playing()
        if current.get("uri") and current.get("uri") != uris[0]:
            switched = await _queue_and_skip(uris[0], device)
            if switched:
                return switched

    result = await _api("PUT", "/me/player/play", params=params, json_body=json_body)
    if isinstance(result, dict) and result.get("error"):
        # Retry once after a forced transfer — keep playback alive (play=True).
        ready = await ensure_device(force_transfer=True, resume=True)
        if ready.get("error"):
            return ready
        device = ready.get("device") or device
        device_id = device.get("id")
        params = {"device_id": device_id} if device_id else None
        result = await _api("PUT", "/me/player/play", params=params, json_body=json_body)
    if isinstance(result, dict) and result.get("error"):
        if len(uris) == 1:
            switched = await _queue_and_skip(uris[0], device)
            if switched:
                return switched
        return result

    # Verify track actually changed; Spotify may 204-success while still on the old song.
    if len(uris) == 1:
        await asyncio.sleep(0.6)
        verify = await now_playing()
        if verify.get("uri") != uris[0]:
            switched = await _queue_and_skip(uris[0], device)
            if switched:
                return switched
            return {
                "error": (
                    "Spotify accepted play but stayed on the previous track. "
                    "Click the Spotify window once, then ask again."
                ),
                "still_playing": verify,
            }
    return {"ok": True, "device": device, **({} if result.get("ok") else {"raw": result})}


async def control(action: str, query: str = "") -> dict:
    """Map HIVE spotify_control actions onto the Web API."""
    action = (action or "").strip().lower()
    query = (query or "").strip()

    try:
        if action in ("now_playing", "status", "current"):
            return await now_playing()

        if action in ("devices", "list_devices"):
            return await list_devices()

        if action == "pause":
            ready = await ensure_device()
            if ready.get("error"):
                return ready
            result = await _api("PUT", "/me/player/pause")
            return result if result.get("error") else {"ok": True, "action": "pause"}

        if action in ("resume", "unpause"):
            result = await _play_body({})
            return result if result.get("error") else {"ok": True, "action": "resume"}

        if action in ("next", "skip"):
            ready = await ensure_device()
            if ready.get("error"):
                return ready
            result = await _api("POST", "/me/player/next")
            return result if result.get("error") else {"ok": True, "action": "next"}

        if action in ("previous", "prev"):
            ready = await ensure_device()
            if ready.get("error"):
                return ready
            result = await _api("POST", "/me/player/previous")
            return result if result.get("error") else {"ok": True, "action": "previous"}

        if action in ("play", "play_playlist", "search_play", "start"):
            if not query:
                result = await _play_body({})
                return result if result.get("error") else {"ok": True, "action": "play"}
            found = await search(query, search_type="track,playlist", limit=5)
            if found.get("error"):
                return found
            chosen = None
            body: dict
            if action == "play_playlist" or "playlist" in query.lower():
                if found.get("playlists"):
                    chosen = found["playlists"][0]
                    body = {"context_uri": chosen["uri"]}
                elif found.get("tracks"):
                    chosen = found["tracks"][0]
                    body = {"uris": [chosen["uri"]]}
                else:
                    return {"error": f"No Spotify results for “{query}”."}
            elif found.get("tracks"):
                chosen = found["tracks"][0]
                body = {"uris": [chosen["uri"]]}
            elif found.get("playlists"):
                chosen = found["playlists"][0]
                body = {"context_uri": chosen["uri"]}
            else:
                return {"error": f"No Spotify results for “{query}”."}
            result = await _play_body(body)
            if result.get("error"):
                return result
            return {
                "ok": True,
                "action": "play",
                "playing": chosen,
                "query": query,
                "device": result.get("device"),
            }

        return {
            "error": (
                f"Unknown action “{action}”. Use play, pause, resume, next, previous, now_playing."
            )
        }
    except SpotifyNotConfigured as exc:
        return {"error": str(exc)}
    except SpotifyNotConnected as exc:
        return {"error": str(exc)}
    except Exception as exc:
        logger.exception("spotify control failed")
        return {"error": f"Spotify API error: {exc}"}
