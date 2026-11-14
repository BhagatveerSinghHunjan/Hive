"""Customer-facing setup: save keys to .env and connect Google/Spotify from the app."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any

# Keys customers can set from Settings. Never return raw secret values.
EDITABLE_KEYS = (
    "HIVE_LLM_API_KEY",
    "DASHSCOPE_API_KEY",
    "HIVE_LLM_BASE_URL",
    "HIVE_LLM_MODEL",
    "EXA_API_KEY",
    "HIVE_TIMEZONE",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "SPOTIFY_CLIENT_ID",
    "SPOTIFY_CLIENT_SECRET",
    "SPOTIFY_REDIRECT_URI",
)

SECRET_KEYS = {
    "HIVE_LLM_API_KEY",
    "DASHSCOPE_API_KEY",
    "EXA_API_KEY",
    "GOOGLE_CLIENT_SECRET",
    "SPOTIFY_CLIENT_SECRET",
}


def env_file_path() -> Path:
    root = (os.environ.get("HIVE_ROOT") or "").strip()
    if root:
        return Path(root).expanduser() / ".env"
    return Path(__file__).resolve().parent.parent / ".env"


def _mask(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if len(raw) <= 8:
        return "••••••••"
    return f"{raw[:4]}…{raw[-4:]}"


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, rest = stripped.partition("=")
        key = key.strip()
        if not key:
            continue
        val = rest.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        values[key] = val
    return values


def _upsert_env_file(path: Path, updates: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(updates)
    out: list[str] = []
    key_re = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=")

    for line in existing_lines:
        match = key_re.match(line.strip()) if line.strip() and not line.strip().startswith("#") else None
        if not match:
            out.append(line)
            continue
        key = match.group(1)
        if key in remaining:
            out.append(f"{key}={remaining.pop(key)}")
        else:
            out.append(line)

    if remaining:
        if out and out[-1].strip():
            out.append("")
        out.append("# Updated from HIVE Desktop Settings")
        for key, value in remaining.items():
            out.append(f"{key}={value}")

    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _apply_runtime_env(updates: dict[str, str]) -> None:
    """Keep the running process in sync so Connect works without a full restart."""
    for key, value in updates.items():
        os.environ[key] = value

    import hive.config as cfg

    cfg.DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
    cfg.LLM_API_KEY = (
        os.environ.get("HIVE_LLM_API_KEY", "").strip()
        or os.environ.get("DASHSCOPE_API_KEY", "").strip()
    )
    cfg.LLM_BASE_URL = (
        os.environ.get("HIVE_LLM_BASE_URL", "").strip() or cfg.QWEN_BASE_URL
    )
    cfg.LLM_MODEL = (
        os.environ.get("HIVE_LLM_MODEL", "").strip()
        or os.environ.get("QWEN_MODEL", cfg.QWEN_MODEL)
    )
    cfg.EXA_API_KEY = os.environ.get("EXA_API_KEY", "")
    cfg.HIVE_TIMEZONE = os.environ.get("HIVE_TIMEZONE", cfg.HIVE_TIMEZONE)
    cfg.GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    cfg.GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    cfg.SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    cfg.SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
    cfg.SPOTIFY_REDIRECT_URI = os.environ.get(
        "SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8899/callback"
    ).strip()

    try:
        import hive.integrations.google_auth as ga

        ga.GOOGLE_CLIENT_ID = cfg.GOOGLE_CLIENT_ID
        ga.GOOGLE_CLIENT_SECRET = cfg.GOOGLE_CLIENT_SECRET
    except Exception:
        pass


def setup_status() -> dict[str, Any]:
    path = env_file_path()
    file_vals = _read_env_file(path)

    def present(key: str) -> bool:
        return bool((os.environ.get(key) or file_vals.get(key) or "").strip())

    def value_for(key: str) -> str:
        return (os.environ.get(key) or file_vals.get(key) or "").strip()

    llm_key = value_for("HIVE_LLM_API_KEY") or value_for("DASHSCOPE_API_KEY")
    fields = {}
    for key in EDITABLE_KEYS:
        raw = value_for(key)
        fields[key] = {
            "set": bool(raw),
            "masked": _mask(raw) if key in SECRET_KEYS else "",
            "value": "" if key in SECRET_KEYS else raw,
        }

    google_connected = False
    google_email = None
    google_error = None
    try:
        from hive.integrations.google_auth import google_auth

        st = google_auth.status(verify=False)
        google_connected = bool(st.get("connected"))
        google_email = st.get("email")
    except Exception as exc:
        google_error = str(exc)[:200]

    spotify_connected = False
    spotify_name = None
    try:
        from hive.integrations import spotify as sp

        spotify_connected = sp.connected()
        if spotify_connected:
            # Lightweight — avoid network if possible
            spotify_name = "connected"
    except Exception:
        pass

    return {
        "ok": True,
        "env_file": str(path),
        "llm_ready": bool(llm_key),
        "exa_ready": present("EXA_API_KEY"),
        "google_client_ready": present("GOOGLE_CLIENT_ID") and present("GOOGLE_CLIENT_SECRET"),
        "spotify_client_ready": present("SPOTIFY_CLIENT_ID")
        and present("SPOTIFY_CLIENT_SECRET"),
        "google_connected": google_connected,
        "google_email": google_email,
        "google_error": google_error,
        "spotify_connected": spotify_connected,
        "spotify_label": spotify_name,
        "timezone": value_for("HIVE_TIMEZONE") or "Asia/Kolkata",
        "model": value_for("HIVE_LLM_MODEL") or value_for("QWEN_MODEL") or "",
        "fields": fields,
        "needs_setup": not bool(llm_key),
    }


def save_secrets(values: dict[str, Any] | None) -> dict[str, Any]:
    values = values or {}
    updates: dict[str, str] = {}
    for key in EDITABLE_KEYS:
        if key not in values:
            continue
        raw = values.get(key)
        if raw is None:
            continue
        text = str(raw).strip()
        # Empty secret fields mean "leave unchanged"
        if not text and key in SECRET_KEYS:
            continue
        updates[key] = text

    if not updates:
        return {"ok": False, "error": "No settings to save."}

    path = env_file_path()
    _upsert_env_file(path, updates)
    _apply_runtime_env(updates)

    restart_required = any(
        key in updates
        for key in (
            "HIVE_LLM_API_KEY",
            "DASHSCOPE_API_KEY",
            "HIVE_LLM_BASE_URL",
            "HIVE_LLM_MODEL",
        )
    )
    status = setup_status()
    return {
        "ok": True,
        "saved": list(updates.keys()),
        "restart_required": restart_required,
        "message": (
            "Saved. Restart the runtime so chat picks up the new model key."
            if restart_required
            else "Saved."
        ),
        "status": status,
    }


async def connect_google() -> dict[str, Any]:
    from hive.integrations.google_auth import GoogleIntegrationError, google_auth

    try:
        result = await asyncio.to_thread(google_auth.connect)
        status = setup_status()
        return {"ok": True, "message": "Google connected.", "result": result, "status": status}
    except GoogleIntegrationError as exc:
        return {"ok": False, "error": str(exc), "status": setup_status()}
    except Exception as exc:
        return {"ok": False, "error": f"Google connect failed: {exc}", "status": setup_status()}


async def disconnect_google() -> dict[str, Any]:
    from hive.integrations.google_auth import google_auth

    try:
        result = await asyncio.to_thread(google_auth.disconnect)
        return {"ok": True, "message": "Google disconnected.", "result": result, "status": setup_status()}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "status": setup_status()}


async def connect_spotify() -> dict[str, Any]:
    from hive.integrations.spotify import SpotifyError, connect_spotify as _connect

    try:
        result = await asyncio.to_thread(_connect)
        return {"ok": True, "message": "Spotify connected.", "result": result, "status": setup_status()}
    except SpotifyError as exc:
        return {"ok": False, "error": str(exc), "status": setup_status()}
    except Exception as exc:
        return {"ok": False, "error": f"Spotify connect failed: {exc}", "status": setup_status()}


async def disconnect_spotify() -> dict[str, Any]:
    from hive.integrations.spotify import disconnect_spotify as _disconnect

    try:
        result = await asyncio.to_thread(_disconnect)
        return {
            "ok": True,
            "message": "Spotify disconnected.",
            "result": result,
            "status": setup_status(),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "status": setup_status()}
