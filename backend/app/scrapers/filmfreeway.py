"""FilmFreeway scraper.

FilmFreeway has no public API, so this scrapes the public festival page for the
fields that change over time (deadlines, entry fee, runtime cap). Identity fields
(name, city, coords) come from our seed DB.

LEGAL/ETIQUETTE NOTE: scrape responsibly — honor robots.txt, rate-limit, cache
aggressively (we cache for hours), and prefer official data where it exists.
This is provided as a starting scaffold; verify FilmFreeway's current Terms
before running at scale.
"""
from __future__ import annotations
import re

from .base import cache_key, cache_get, cache_set, with_page
from ..config import settings


async def _scrape_one(page, url: str) -> dict:
    await page.goto(url, wait_until="domcontentloaded")
    text = await page.inner_text("body")

    # Entry fee: first "$NN" near the word "Fee" — selectors will need tuning
    fee = None
    m = re.search(r"\$(\d{1,3})", text)
    if m:
        fee = int(m.group(1))

    # Deadlines: look for "Deadline" rows with dates (very rough heuristic)
    deadlines = []
    for label, pat in [
        ("Early", r"Early Bird Deadline\s*([A-Za-z]+ \d{1,2}, \d{4})"),
        ("Regular", r"Regular Deadline\s*([A-Za-z]+ \d{1,2}, \d{4})"),
        ("Late", r"Late Deadline\s*([A-Za-z]+ \d{1,2}, \d{4})"),
    ]:
        dm = re.search(pat, text)
        if dm:
            deadlines.append({"label": label, "raw": dm.group(1)})

    return {"url": url, "base_fee": fee, "deadlines_raw": deadlines}


async def refresh_festival(url: str) -> tuple[dict | None, bool]:
    """Return (scraped_fields, is_live). Falls back to (None, False)."""
    key = cache_key("ff", url)
    cached = cache_get(key)
    if cached is not None:
        return cached, True

    if not settings.enable_live_scraping:
        return None, False

    try:
        data = await with_page(lambda pg: _scrape_one(pg, url))
        cache_set(key, data)
        return data, True
    except Exception as e:  # noqa: BLE001 — fall back, never crash the request
        print(f"[filmfreeway] scrape failed for {url}: {e}")
        return None, False
