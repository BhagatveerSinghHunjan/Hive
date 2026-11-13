"""
Site playbooks — remember how a site/login/checkout works after success.

Stores only URLs, selectors, session names, trust score/level, and replayable
flow steps. Never stores passwords, cookies, or card numbers.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Optional

from hive.config import HIVE_HOME, ensure_dirs

logger = logging.getLogger(__name__)

PLAYBOOK_DIR = HIVE_HOME / "playbooks"
SCHEMA_VERSION = 2
MAX_STEPS = 40


def _site_key(domain_or_url: str) -> str:
    d = (domain_or_url or "").strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = d.split("/", 1)[0]
    d = d.replace("www.", "")
    d = re.sub(r"[^a-z0-9._-]+", "_", d)
    return d or "unknown"


def site_key(domain_or_url: str) -> str:
    return _site_key(domain_or_url)


def _ensure() -> None:
    ensure_dirs()
    PLAYBOOK_DIR.mkdir(parents=True, exist_ok=True)


def _playbook_path(site_key: str) -> Path:
    return PLAYBOOK_DIR / f"{site_key}.json"


def trust_level_for_score(score: int) -> int:
    """Map a 0-100 trust score to the 0-3 autonomy ladder."""
    score = max(0, min(100, int(score or 0)))
    if score >= 85:
        return 3
    if score >= 60:
        return 2
    if score >= 30:
        return 1
    return 0


def _empty(site: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "site": site,
        "trust_score": 0,
        "trust_level": 0,
        "sessions": {},
        "login": {},
        "signup": {},
        "checkout": {},
        "flows": {},
        "updated_at": time.time(),
    }


def _migrate(data: dict[str, Any]) -> dict[str, Any]:
    merged = _empty(data.get("site", "unknown"))
    merged.update(data)
    merged["schema_version"] = SCHEMA_VERSION
    if "trust_level" not in data:
        merged["trust_level"] = trust_level_for_score(merged.get("trust_score", 0))
    if not isinstance(merged.get("flows"), dict):
        merged["flows"] = {}
    return merged


def load_playbook(site_key: str) -> dict[str, Any]:
    """Load playbook JSON for a site. Returns default structure if missing."""
    _ensure()
    site_key = _site_key(site_key)
    path = _playbook_path(site_key)
    if not path.exists():
        return _empty(site_key)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Invalid playbook format")
        return _migrate(data)
    except Exception as e:
        logger.warning("Failed to load playbook %s: %s", path, e)
        return _empty(site_key)


def save_playbook(site_key: str, data: dict[str, Any]) -> None:
    _ensure()
    site_key = _site_key(site_key)
    path = _playbook_path(site_key)
    tmp = path.with_suffix(".json.tmp")
    data = dict(data)
    data["schema_version"] = SCHEMA_VERSION
    data.setdefault("site", site_key)
    data.setdefault("flows", {})
    data["trust_level"] = trust_level_for_score(data.get("trust_score", 0))
    data["updated_at"] = time.time()
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def record_success(
    site_key: str,
    *,
    flow: str,
    session_name: Optional[str] = None,
    last_url: Optional[str] = None,
    note: Optional[str] = None,
    trust_delta: int = 8,
) -> dict[str, Any]:
    """Update playbook after a successful browser workflow."""
    pb = load_playbook(site_key)
    pb["trust_score"] = max(0, min(100, int(pb.get("trust_score", 0)) + int(trust_delta)))

    flow_key = flow.lower().strip()
    if flow_key not in ("login", "signup", "checkout"):
        flow_key = "login"

    flow_obj = dict(pb.get(flow_key) or {})
    flow_obj["last_success_at"] = time.time()
    if session_name:
        flow_obj["session_name"] = session_name
        pb.setdefault("sessions", {})[session_name] = {
            "flow": flow_key,
            "saved_at": time.time(),
        }
    if last_url:
        flow_obj["last_url"] = last_url
    if note:
        flow_obj["note"] = note[:400]

    pb[flow_key] = flow_obj
    pb["trust_level"] = trust_level_for_score(pb["trust_score"])
    save_playbook(site_key, pb)
    return pb


def record_failure(site_key: str, *, flow: str, trust_delta: int = -10) -> dict[str, Any]:
    """Update trust score after a failed browser workflow."""
    pb = load_playbook(site_key)
    pb["trust_score"] = max(0, min(100, int(pb.get("trust_score", 0)) + int(trust_delta)))

    flow_key = flow.lower().strip()
    if flow_key not in ("login", "signup", "checkout"):
        flow_key = "login"
    pb.setdefault(flow_key, {})
    pb[flow_key]["last_failure_at"] = time.time()
    pb["trust_level"] = trust_level_for_score(pb["trust_score"])
    save_playbook(site_key, pb)
    return pb


# ─── Recorded flows (schema v2) ─────────────────────────────────────────


def _clean_steps(steps: list[dict]) -> list[dict]:
    cleaned = []
    for step in steps[:MAX_STEPS]:
        if not isinstance(step, dict):
            continue
        action = str(step.get("action", "")).strip().lower()
        if action not in ("goto", "click", "type", "press", "wait"):
            continue
        item = {"action": action}
        for key in ("url", "selector", "text", "key", "timeout_ms"):
            if step.get(key) not in (None, ""):
                item[key] = step[key]
        if action == "type" and "selector" not in item:
            continue
        if action == "click" and "selector" not in item:
            continue
        cleaned.append(item)
    return cleaned


def save_flow(
    site: str,
    flow: str,
    steps: list[dict],
    *,
    note: str | None = None,
) -> dict[str, Any]:
    """Persist a replayable browser flow under the site playbook."""
    pb = load_playbook(site)
    site = _site_key(site)
    key = (flow or "login").strip().lower().replace(" ", "_")
    cleaned = _clean_steps(steps)
    if not cleaned:
        return pb
    pb.setdefault("flows", {})[key] = {
        "steps": cleaned,
        "note": (note or "")[:400],
        "runs": 0,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    save_playbook(site, pb)
    return pb


def get_flow(site: str, flow: str) -> dict | None:
    pb = load_playbook(site)
    key = (flow or "login").strip().lower().replace(" ", "_")
    data = (pb.get("flows") or {}).get(key)
    if not data:
        legacy = pb.get(key)
        if isinstance(legacy, dict) and legacy.get("steps"):
            return legacy
        return None
    return data


def list_flows(site: str) -> dict:
    pb = load_playbook(site)
    flows = pb.get("flows") or {}
    return {
        "site": site_key(site),
        "trust_score": pb.get("trust_score", 0),
        "trust_level": pb.get("trust_level", 0),
        "flows": {
            name: {
                "steps": len(data.get("steps", [])),
                "runs": data.get("runs", 0),
                "updated_at": data.get("updated_at"),
                "note": data.get("note", ""),
            }
            for name, data in flows.items()
        },
    }


def record_replay(site: str, flow: str, success: bool) -> dict[str, Any]:
    pb = load_playbook(site)
    key = (flow or "login").strip().lower().replace(" ", "_")
    flow_obj = (pb.get("flows") or {}).get(key)
    if flow_obj is not None:
        flow_obj["runs"] = int(flow_obj.get("runs", 0)) + 1
        flow_obj["last_run_at"] = time.time()
        flow_obj["last_result"] = "success" if success else "failure"
    if success:
        pb["trust_score"] = min(100, int(pb.get("trust_score", 0)) + 4)
    else:
        pb["trust_score"] = max(0, int(pb.get("trust_score", 0)) - 4)
    pb["trust_level"] = trust_level_for_score(pb["trust_score"])
    save_playbook(site, pb)
    return pb


def list_playbooks() -> dict:
    _ensure()
    playbooks = []
    for path in sorted(PLAYBOOK_DIR.glob("*.json")):
        site = path.stem
        pb = load_playbook(site)
        playbooks.append({
            "site": site,
            "trust_score": pb.get("trust_score", 0),
            "trust_level": pb.get("trust_level", 0),
            "flows": sorted((pb.get("flows") or {}).keys()),
        })
    return {"count": len(playbooks), "playbooks": playbooks}


def delete_flow(site: str, flow: str) -> bool:
    site = _site_key(site)
    pb = load_playbook(site)
    key = (flow or "").strip().lower().replace(" ", "_")
    flows = pb.get("flows") or {}
    if key not in flows:
        return False
    del flows[key]
    pb["flows"] = flows
    save_playbook(site, pb)
    return True


def delete_playbook(site: str) -> bool:
    _ensure()
    path = _playbook_path(site_key(site))
    if path.exists():
        path.unlink()
        return True
    return False
