"""FilmFreeway catalog scraper.

Crawls FilmFreeway's public festival browse page to discover new festivals and
flag festivals that have disappeared.  Results are never auto-published:
  - New slugs   → status='pending_review'  (human must approve)
  - Known active slugs that vanished → status='inactive_review'  (human must confirm)

LEGAL NOTE: Verify FilmFreeway's current ToS and robots.txt before running at
volume.  This scraper rate-limits itself and caches results aggressively.
"""
from __future__ import annotations
import re
from datetime import datetime, timezone

from .base import cache_key, cache_get, cache_set, with_page
from ..config import settings

# US festival browse URL — adjust country_code or filters as needed
_BROWSE_URL = (
    "https://filmfreeway.com/festivals"
    "?utf8=%E2%9C%93&q=&country_code=US&sort=popular"
)

# How many "End" keypresses to trigger infinite-scroll loading
_SCROLL_PASSES = 8


async def _scrape_browse(page) -> list[dict]:
    """Return a list of {name, filmfreeway_url, slug} dicts found on the browse page.

    FilmFreeway renders festival cards via React; selectors will drift over time —
    this is expected per CLAUDE.md.  The regex below is the stable contract:
    festival pages live at /festivals/<slug> with no further path segments.
    """
    await page.goto(_BROWSE_URL, wait_until="networkidle", timeout=60_000)

    # Trigger infinite-scroll / lazy loading
    for _ in range(_SCROLL_PASSES):
        await page.keyboard.press("End")
        await page.wait_for_timeout(700)

    anchors = await page.query_selector_all("a[href]")
    seen: set[str] = set()
    results: list[dict] = []

    for anchor in anchors:
        href = (await anchor.get_attribute("href") or "").strip()
        # Match only /festivals/<slug> — no sub-paths, no query strings
        if not re.match(r"^/festivals/[A-Za-z0-9_-]+$", href):
            continue
        slug = href.split("/")[-1]
        # Skip well-known non-festival slugs that share the URL pattern
        if slug in seen or slug in {"submit", "help", "login", "signup", "pricing"}:
            continue
        seen.add(slug)

        # Best-effort name extraction; falls back to slug if element is empty
        try:
            raw = (
                await anchor.get_attribute("title")
                or await anchor.get_attribute("aria-label")
                or await anchor.inner_text()
                or slug
            )
            name = raw.strip()[:200] or slug
        except Exception:  # noqa: BLE001
            name = slug

        results.append(
            {
                "name": name,
                "filmfreeway_url": f"https://filmfreeway.com{href}",
                "slug": slug,
            }
        )

    return results


async def sync_catalog(db_session) -> dict:
    """Scrape the browse page and reconcile against the DB.

    Returns a summary dict; never raises (falls back with error key).
    Requires ENABLE_LIVE_SCRAPING=True in .env, otherwise skips.
    """
    if not settings.enable_live_scraping:
        return {"skipped": True, "reason": "live scraping disabled"}

    # Catalog sync is expensive — cache the summary for the same TTL as other scrapers
    ck = cache_key("catalog_sync_v1")
    cached = cache_get(ck)
    if cached is not None:
        return {"skipped": True, "reason": "recently synced", "last": cached}

    try:
        scraped = await with_page(_scrape_browse)
    except Exception as exc:  # noqa: BLE001 — never crash the scheduler
        return {"error": str(exc)}

    scraped_urls = {f["filmfreeway_url"] for f in scraped}

    from sqlalchemy import select
    from ..db import FestivalRow

    result = await db_session.execute(select(FestivalRow))
    known: dict[str, FestivalRow] = {
        row.filmfreeway_url: row for row in result.scalars().all()
    }

    now = datetime.now(timezone.utc).isoformat()
    added = flagged = 0

    for f in scraped:
        url = f["filmfreeway_url"]
        if url not in known:
            db_session.add(
                FestivalRow(
                    name=f["name"],
                    filmfreeway_url=url,
                    city="",
                    lat=0.0,
                    lng=0.0,
                    genres="[]",
                    deadlines="[]",
                    status="pending_review",
                    last_scraped_at=now,
                )
            )
            added += 1

    for url, row in known.items():
        if row.status == "active" and url not in scraped_urls:
            row.status = "inactive_review"
            flagged += 1

    await db_session.commit()

    summary = {
        "added_pending": added,
        "flagged_inactive_review": flagged,
        "total_scraped": len(scraped),
        "synced_at": now,
    }
    cache_set(ck, summary)
    return summary
