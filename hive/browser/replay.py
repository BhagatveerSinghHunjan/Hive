"""Replay recorded browser flows from site playbooks."""

from __future__ import annotations

import logging
import re

from hive.playbooks import get_flow, load_playbook, record_failure, record_replay, site_key
from hive.playbooks import record_success

logger = logging.getLogger(__name__)

_PLACEHOLDER = re.compile(r"\$\{([a-zA-Z0-9_]+)\}")


def _substitute(text: str, sensitive_data: dict | None) -> tuple[str, list[str]]:
    missing = []

    def _replace(match):
        key = match.group(1)
        if sensitive_data and key in sensitive_data:
            return str(sensitive_data[key])
        missing.append(key)
        return ""

    return _PLACEHOLDER.sub(_replace, text or ""), missing


async def replay_flow(
    site: str,
    flow: str = "login",
    session_id: str | None = None,
    sensitive_data: dict | None = None,
    stop_on_error: bool = True,
    page=None,
) -> dict:
    """Replay a stored flow in the persistent browser pool.

    Returns a credential-safe report; sensitive values are never echoed.
    """
    key = site_key(site)
    data = get_flow(key, flow)
    if not data or not data.get("steps"):
        return {
            "status": "not_found",
            "site": key,
            "flow": flow,
            "error": f"No recorded flow '{flow}' for {key}",
        }

    if page is None:
        from hive.browser.pool import get_pool

        page = await get_pool().get_page(session_id)
    steps = data.get("steps", [])
    executed = 0
    errors: list[str] = []
    masked_missing: list[str] = []

    for index, step in enumerate(steps):
        action = step.get("action")
        try:
            if action == "goto":
                await page.goto(step.get("url", ""), wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(800)
            elif action == "click":
                selector = step.get("selector", "")
                await page.click(selector, timeout=8000)
                await page.wait_for_load_state("domcontentloaded", timeout=10000)
            elif action == "type":
                selector = step.get("selector", "")
                text, missing = _substitute(step.get("text", ""), sensitive_data)
                masked_missing.extend(missing)
                if missing:
                    errors.append(f"step {index + 1}: missing sensitive keys {missing}")
                    if stop_on_error:
                        break
                    continue
                await page.fill(selector, text, timeout=8000)
            elif action == "press":
                selector = step.get("selector")
                if selector:
                    await page.press(selector, step.get("key", "Enter"), timeout=8000)
                else:
                    await page.keyboard.press(step.get("key", "Enter"))
            elif action == "wait":
                await page.wait_for_timeout(max(100, int(step.get("timeout_ms", 1000))))
            executed += 1
        except Exception as exc:
            errors.append(f"step {index + 1} ({action}): {str(exc)[:160]}")
            if stop_on_error:
                break

    success = executed == len(steps) and not errors
    if success:
        record_replay(key, flow, True)
        record_success(key, flow=flow, last_url=page.url, note=f"replay:{flow}")
    else:
        record_replay(key, flow, False)
        record_failure(key, flow=flow)

    return {
        "status": "replayed" if success else "failed",
        "site": key,
        "flow": flow,
        "steps_total": len(steps),
        "steps_executed": executed,
        "errors": errors,
        "missing_sensitive_keys": sorted(set(masked_missing)),
        "trust_level": load_playbook(key).get("trust_level", 0),
    }
