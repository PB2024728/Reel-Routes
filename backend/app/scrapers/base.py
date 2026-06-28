"""Shared scraper plumbing: TTL cache, distance math, and a Playwright helper.

Every scraper module follows the same contract:
    async def fetch(...) -> tuple[list[dict], bool]   # (rows, is_live)

When ENABLE_LIVE_SCRAPING is False (default) or a scrape fails, modules return
sample/estimated rows with is_live=False so the app always responds.
"""
from __future__ import annotations
import time
import math
import hashlib
import json
from typing import Any, Callable, Awaitable

from ..config import settings

# ---------- tiny in-memory TTL cache (swap for Redis in production) ----------
_CACHE: dict[str, tuple[float, Any]] = {}


def cache_key(*parts: Any) -> str:
    raw = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def cache_get(key: str):
    hit = _CACHE.get(key)
    if not hit:
        return None
    ts, val = hit
    if time.time() - ts > settings.scrape_cache_ttl_minutes * 60:
        _CACHE.pop(key, None)
        return None
    return val


def cache_set(key: str, val: Any):
    _CACHE[key] = (time.time(), val)


# ---------- geo ----------
def haversine_mi(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ---------- Playwright helper ----------
async def with_page(coro: Callable[[Any], Awaitable[Any]]):
    """Open a Playwright page, run coro(page), always clean up.

    Requires: pip install playwright && playwright install chromium
    Returns whatever coro returns, or raises so the caller can fall back.
    """
    from playwright.async_api import async_playwright  # imported lazily

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=settings.playwright_headless)
        try:
            ctx = await browser.new_context(user_agent=settings.user_agent)
            page = await ctx.new_page()
            page.set_default_timeout(settings.scrape_timeout_seconds * 1000)
            return await coro(page)
        finally:
            await browser.close()
