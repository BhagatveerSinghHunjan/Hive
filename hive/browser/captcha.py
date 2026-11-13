"""CAPTCHA handling — human handoff by default, optional external solver.

Set HIVE_CAPTCHA_PROVIDER=2captcha and HIVE_CAPTCHA_API_KEY to enable the
optional reCAPTCHA v2 solver. Human handoff always remains the fallback.
"""

from __future__ import annotations

import asyncio
import logging
import re

from hive.config import (
    HIVE_CAPTCHA_API_KEY,
    HIVE_CAPTCHA_PROVIDER,
    HIVE_CAPTCHA_TIMEOUT,
)

logger = logging.getLogger(__name__)

CAPTCHA_INDICATORS = (
    "captcha", "recaptcha", "hcaptcha", "challenge",
    "verify you are human", "i'm not a robot", "security check",
)

_SITEKEY_RE = re.compile(r'data-sitekey=["\']([^"\']+)["\']', re.IGNORECASE)


def detect_from_elements(elements: list) -> bool:
    for el in elements or []:
        combined = " ".join([
            (el.get("text") or ""),
            (el.get("placeholder") or ""),
            (el.get("ariaLabel") or ""),
            (el.get("selector") or ""),
        ]).lower()
        if any(indicator in combined for indicator in CAPTCHA_INDICATORS):
            return True
    return False


async def detect_from_page(page) -> bool:
    try:
        html = (await page.content())[:200000].lower()
    except Exception:
        return False
    return any(indicator in html for indicator in CAPTCHA_INDICATORS)


async def _solve_recaptcha_v2(page) -> bool:
    """Best-effort 2captcha reCAPTCHA v2 solve. Returns True when token injected."""
    if not HIVE_CAPTCHA_API_KEY:
        logger.info("2captcha selected but HIVE_CAPTCHA_API_KEY is empty")
        return False

    try:
        html = await page.content()
    except Exception as exc:
        logger.warning("Could not read page for CAPTCHA solving: %s", exc)
        return False

    match = _SITEKEY_RE.search(html)
    if not match:
        logger.info("No reCAPTCHA sitekey found; falling back to human handoff")
        return False

    sitekey = match.group(1)
    page_url = page.url

    import httpx

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            created = await client.post(
                "https://2captcha.com/in.php",
                data={
                    "key": HIVE_CAPTCHA_API_KEY,
                    "method": "userrecaptcha",
                    "googlekey": sitekey,
                    "pageurl": page_url,
                    "json": 1,
                },
            )
            payload = created.json()
            if payload.get("status") != 1:
                logger.warning("2captcha submit failed: %s", payload.get("request"))
                return False
            request_id = payload.get("request")

            waited = 0
            while waited < HIVE_CAPTCHA_TIMEOUT:
                await asyncio.sleep(5)
                waited += 5
                result = await client.get(
                    "https://2captcha.com/res.php",
                    params={
                        "key": HIVE_CAPTCHA_API_KEY,
                        "action": "get",
                        "id": request_id,
                        "json": 1,
                    },
                )
                data = result.json()
                if data.get("status") == 1:
                    token = data.get("request", "")
                    if token:
                        await page.evaluate(
                            """(token) => {
                                const textarea = document.querySelector(
                                    'textarea[name="g-recaptcha-response"], #g-recaptcha-response'
                                );
                                if (textarea) {
                                    textarea.value = token;
                                    textarea.dispatchEvent(new Event('input', { bubbles: true }));
                                    textarea.dispatchEvent(new Event('change', { bubbles: true }));
                                }
                            }""",
                            token,
                        )
                        return True
                elif data.get("request") not in ("CAPCHA_NOT_READY",):
                    logger.warning("2captcha solve failed: %s", data.get("request"))
                    return False
    except Exception as exc:
        logger.warning("2captcha solve error: %s", exc)
        return False
    return False


async def handle_captcha(
    site: str,
    url: str = "",
    page=None,
    elements: list | None = None,
) -> dict:
    """Try the configured solver, then fall back to human handoff."""
    provider = HIVE_CAPTCHA_PROVIDER

    solved = False
    if provider == "2captcha" and page is not None:
        solved = await _solve_recaptcha_v2(page)

    if not solved:
        from hive.interactive import prompt_captcha_handoff

        try:
            solved = bool(await prompt_captcha_handoff(site, url))
        except Exception as exc:
            logger.warning("CAPTCHA human handoff failed: %s", exc)
            solved = False

    return {
        "status": "solved" if solved else "captcha_required",
        "provider": provider if provider == "2captcha" else "human",
        "requires_human": not solved,
    }
