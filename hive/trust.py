"""Trust ladder — per-domain browser autonomy levels.

Levels
- 0: ask for every browser action
- 1: learned — still ask (future: ask once per session)
- 2: trusted for navigation/reading, still ask before form submissions
- 3: autonomous for safe/moderate browser actions

Outbound actions (email sends, calendar invites, checkout, signup) are NEVER
covered by the trust ladder; they always require human approval.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path

from hive.config import HIVE_HOME, HIVE_TRUST_DEFAULT_LEVEL

logger = logging.getLogger(__name__)

TRUST_FILE = HIVE_HOME / "trust.json"
VALID_LEVELS = (0, 1, 2, 3)

NEVER_AUTONOMOUS = {
    "browser_checkout",
    "browser_signup",
    "gmail_send_draft",
    "gmail_send_message",
    "calendar_create_event",
    "calendar_update_event",
    "calendar_delete_event",
}


def _domain(value: str) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"^https?://", "", text)
    text = text.split("/", 1)[0].split(":", 1)[0]
    return text.replace("www.", "")


def _load() -> dict:
    path = Path(TRUST_FILE)
    if not path.exists():
        return {"version": 1, "default_level": HIVE_TRUST_DEFAULT_LEVEL, "domains": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("invalid trust file")
    except Exception as exc:
        logger.warning("Could not read trust file: %s", exc)
        return {"version": 1, "default_level": HIVE_TRUST_DEFAULT_LEVEL, "domains": {}}
    data.setdefault("default_level", HIVE_TRUST_DEFAULT_LEVEL)
    data.setdefault("domains", {})
    return data


def _save(data: dict) -> None:
    path = Path(TRUST_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    data["updated_at"] = time.time()
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def get_level(domain_or_url: str) -> int:
    domain = _domain(domain_or_url)
    if not domain:
        return int(HIVE_TRUST_DEFAULT_LEVEL)
    data = _load()
    entry = (data.get("domains") or {}).get(domain)
    if entry is None:
        return int(data.get("default_level", 0))
    return int(entry.get("level", 0))


def has_explicit_level(domain_or_url: str) -> bool:
    domain = _domain(domain_or_url)
    return domain in (_load().get("domains") or {})


def set_level(domain_or_url: str, level: int) -> dict:
    try:
        level = int(level)
    except (TypeError, ValueError):
        return {"error": f"level must be one of {VALID_LEVELS}"}
    if level not in VALID_LEVELS:
        return {"error": f"level must be one of {VALID_LEVELS}"}
    domain = _domain(domain_or_url)
    if not domain:
        return {"error": "domain is required"}
    data = _load()
    data.setdefault("domains", {})[domain] = {
        "level": level,
        "updated_at": time.time(),
    }
    _save(data)
    return {"status": "updated", "domain": domain, "level": level}


def list_levels() -> dict:
    data = _load()
    return {
        "default_level": int(data.get("default_level", 0)),
        "count": len(data.get("domains") or {}),
        "domains": [
            {"domain": domain, "level": entry.get("level", 0)}
            for domain, entry in sorted((data.get("domains") or {}).items())
        ],
    }


def can_auto_allow(tool_name: str, target: str = "") -> bool | None:
    """Return True/False when an explicit trust level decides, else None.

    Only browser actions are affected. Unknown domains fall back to existing
    permission behavior (None) unless HIVE_TRUST_STRICT=true.
    """
    if tool_name in NEVER_AUTONOMOUS:
        return False
    if not tool_name.startswith("browser_"):
        return None
    domain = _domain(target)
    if not domain:
        return None
    if not has_explicit_level(domain):
        strict = os.environ.get("HIVE_TRUST_STRICT", "false").lower() in ("1", "true", "yes")
        if not strict:
            return None
        level = get_level(domain)
    else:
        level = get_level(domain)
    if tool_name in ("browser_open", "browser_read", "browser_inspect",
                     "browser_screenshot", "browser_back", "browser_wait"):
        return level >= 2
    return level >= 3


def format_levels_text() -> str:
    data = list_levels()
    lines = [f"Trust ladder (default level {data['default_level']})"]
    if not data["domains"]:
        lines.append("- (no per-domain overrides)")
    for entry in data["domains"]:
        lines.append(f"- {entry['domain']}: level {entry['level']}")
    lines.append("Set with: /trust <domain> <0-3>")
    return "\n".join(lines)
