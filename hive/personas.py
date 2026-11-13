"""Digital-twin personas — isolated vaults, spend caps, and browser profiles."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from hive.config import HIVE_HOME, HIVE_PERSONA, HIVE_PERSONA_FILE

logger = logging.getLogger(__name__)

DEFAULT_PERSONA = "default"


def _default_file() -> dict:
    return {
        "version": 1,
        "active": HIVE_PERSONA or DEFAULT_PERSONA,
        "personas": {
            DEFAULT_PERSONA: {
                "label": "Default",
                "vault_dir": str(Path(HIVE_HOME) / "vault"),
                "browser_profile": "default",
                "max_order_amount": None,
                "max_daily_spend": None,
            }
        },
    }


def _load() -> dict:
    path = Path(HIVE_PERSONA_FILE)
    if not path.exists():
        return _default_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("invalid personas file")
    except Exception as exc:
        logger.warning("Could not read personas file: %s", exc)
        return _default_file()
    data.setdefault("active", DEFAULT_PERSONA)
    personas = data.setdefault("personas", {})
    personas.setdefault(DEFAULT_PERSONA, _default_file()["personas"][DEFAULT_PERSONA])
    return data


def _save(data: dict) -> None:
    path = Path(HIVE_PERSONA_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    data["updated_at"] = time.time()
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def list_personas() -> dict:
    data = _load()
    return {
        "active": data.get("active", DEFAULT_PERSONA),
        "count": len(data.get("personas") or {}),
        "personas": [
            {
                "name": name,
                "label": spec.get("label", name),
                "vault_dir": spec.get("vault_dir"),
                "browser_profile": spec.get("browser_profile", name),
                "max_order_amount": spec.get("max_order_amount"),
                "max_daily_spend": spec.get("max_daily_spend"),
                "active": name == data.get("active"),
            }
            for name, spec in sorted((data.get("personas") or {}).items())
        ],
    }


def create_persona(name: str, label: str = "", max_order_amount=None,
                   max_daily_spend=None) -> dict:
    name = (name or "").strip().lower().replace(" ", "_")
    if not name:
        return {"error": "persona name is required"}
    if not name.replace("_", "").replace("-", "").isalnum():
        return {"error": "persona name must be alphanumeric (underscores allowed)"}

    data = _load()
    if name in data.get("personas", {}):
        return {"error": f"persona already exists: {name}"}

    vault_dir = Path(HIVE_HOME) / "personas" / name / "vault"
    data.setdefault("personas", {})[name] = {
        "label": label or name.replace("_", " ").title(),
        "vault_dir": str(vault_dir),
        "browser_profile": f"persona_{name}",
        "max_order_amount": max_order_amount,
        "max_daily_spend": max_daily_spend,
        "created_at": time.time(),
    }
    _save(data)
    return {"status": "created", "persona": name, "vault_dir": str(vault_dir)}


def active_persona() -> dict:
    data = _load()
    name = data.get("active", DEFAULT_PERSONA)
    spec = (data.get("personas") or {}).get(name) or {}
    return {"name": name, **spec}


def use_persona(name: str) -> dict:
    name = (name or "").strip().lower()
    data = _load()
    if name not in (data.get("personas") or {}):
        return {"error": f"unknown persona: {name}"}
    data["active"] = name
    _save(data)
    applied = apply_persona(name)
    return {"status": "active", "persona": name, **applied}


def apply_persona(name: str | None = None) -> dict:
    """Apply persona settings to already-imported modules (best effort)."""
    persona = active_persona() if not name else {
        "name": name,
        **(_load().get("personas", {}).get(name) or {}),
    }
    if not persona or persona.get("name") == DEFAULT_PERSONA:
        return {"applied": False, "reason": "default persona uses standard paths"}

    applied = {"applied": True, "vault": False, "checkout": False}

    vault_dir = persona.get("vault_dir")
    if vault_dir:
        try:
            from hive.browser import vault as vault_module
            vault_path = Path(vault_dir).expanduser()
            vault_module.VAULT_DIR = vault_path
            vault_module.VAULT_FILE = vault_path / "secrets.enc"
            vault_path.mkdir(parents=True, exist_ok=True)
            applied["vault"] = True
        except Exception as exc:
            logger.warning("Could not apply persona vault: %s", exc)

    try:
        from hive.browser import checkout as checkout_module
        if persona.get("max_order_amount") not in (None, ""):
            checkout_module.MAX_ORDER_AMOUNT = float(persona["max_order_amount"])
        if persona.get("max_daily_spend") not in (None, ""):
            checkout_module.MAX_DAILY_SPEND = float(persona["max_daily_spend"])
        spend_dir = Path(HIVE_HOME) / "personas" / persona["name"]
        spend_dir.mkdir(parents=True, exist_ok=True)
        checkout_module.SPEND_LOG = spend_dir / "checkout_spend.json"
        applied["checkout"] = True
    except Exception as exc:
        logger.warning("Could not apply persona checkout caps: %s", exc)

    return applied


def apply_active_persona() -> dict:
    try:
        return apply_persona(active_persona().get("name"))
    except Exception:
        return {"applied": False}


def format_personas_text() -> str:
    listing = list_personas()
    lines = [f"Personas (active: {listing['active']})"]
    for persona in listing["personas"]:
        marker = "*" if persona["active"] else "-"
        lines.append(
            f"{marker} {persona['name']} — {persona['label']} "
            f"(profile {persona['browser_profile']})"
        )
    lines.append("Use: /persona use <name> · /persona create <name> [label]")
    return "\n".join(lines)
