"""Record browser actions into replayable playbook flows.

Only structural information is stored: URLs, stable selectors, and text with
``${key}`` placeholders for sensitive values. Passwords/card data never touch
the playbook.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from hive.playbooks import save_flow, site_key

logger = logging.getLogger(__name__)

_SELECTOR_JS = """(el) => {
    if (!el || el.nodeType !== 1) return null;
    if (el.id) return `#${CSS.escape(el.id)}`;
    for (const attr of ['data-testid', 'data-test', 'name', 'aria-label', 'placeholder']) {
        const value = el.getAttribute(attr);
        if (value) return `${el.tagName.toLowerCase()}[${attr}="${value.replace(/"/g, '\\\\"')}"]`;
    }
    if (el.tagName === 'A' && el.getAttribute('href')) {
        return `a[href="${el.getAttribute('href')}"]`;
    }
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 5) {
        let part = node.tagName.toLowerCase();
        const parent = node.parentElement;
        if (parent) {
            const siblings = Array.from(parent.children).filter(c => c.tagName === node.tagName);
            if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
        }
        parts.unshift(part);
        node = parent;
    }
    return parts.join(' > ');
}"""


async def selector_for(page, element, fallback: str = "") -> str:
    """Best-effort stable CSS selector for a Playwright element handle."""
    if fallback:
        return fallback
    try:
        selector = await element.evaluate(_SELECTOR_JS)
        return selector or ""
    except Exception:
        return ""


class BrowserRecorder:
    """Collects steps during a recording session and saves them on stop."""

    def __init__(self) -> None:
        self.active = False
        self.site = ""
        self.flow = "login"
        self.steps: list[dict[str, Any]] = []
        self.note = ""

    def start(self, name: str = "login", site: str = "", note: str = "") -> dict:
        self.active = True
        self.site = site_key(site) if site else ""
        self.flow = (name or "login").strip().lower().replace(" ", "_")
        self.steps = []
        self.note = note
        return {
            "status": "recording",
            "site": self.site or "(set on first navigation)",
            "flow": self.flow,
        }

    def stop(self, save: bool = True) -> dict:
        steps = list(self.steps)
        self.active = False
        if not save:
            self.steps = []
            return {"status": "discarded", "steps": len(steps)}
        if not self.site or not steps:
            self.steps = []
            return {
                "status": "nothing_saved",
                "reason": "No site/actions captured. Set site= when starting.",
                "steps": len(steps),
            }
        save_flow(self.site, self.flow, steps, note=self.note)
        self.steps = []
        return {
            "status": "saved",
            "site": self.site,
            "flow": self.flow,
            "steps": len(steps),
        }

    def _add(self, step: dict) -> None:
        if self.active and len(self.steps) < 40:
            self.steps.append(step)

    def record_goto(self, url: str) -> None:
        if not self.site and url:
            self.site = site_key(url)
        self._add({"action": "goto", "url": url})

    def record_click(self, selector: str) -> None:
        if selector:
            self._add({"action": "click", "selector": selector})

    def record_type(self, selector: str, text: str, press_enter: bool = False) -> None:
        if not selector:
            return
        self._add({"action": "type", "selector": selector, "text": text})
        if press_enter:
            self._add({"action": "press", "selector": selector, "key": "Enter"})

    def record_wait(self, timeout_ms: int = 1000) -> None:
        self._add({"action": "wait", "timeout_ms": max(100, int(timeout_ms))})

    def record_press(self, key: str, selector: str = "") -> None:
        step = {"action": "press", "key": key}
        if selector:
            step["selector"] = selector
        self._add(step)

    def snapshot(self) -> dict:
        return {
            "active": self.active,
            "site": self.site,
            "flow": self.flow,
            "steps": list(self.steps),
        }


_recorder = BrowserRecorder()


def get_recorder() -> BrowserRecorder:
    return _recorder
