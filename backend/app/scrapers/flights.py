"""Flight pricing.

Strategy:
  1. If AMADEUS creds are set, use the official API (most reliable) — stub provided.
  2. Else if live scraping enabled, scrape a metasearch results page via Playwright.
  3. Else return a distance-based estimate.

Always returns a real Google Flights deep-link so the user can book immediately.
"""
from __future__ import annotations
import urllib.parse

from .base import cache_key, cache_get, cache_set, with_page
from ..config import settings


def google_flights_link(origin_city: str, dest_city: str, date_iso: str) -> str:
    q = f"flights from {origin_city} to {dest_city} on {date_iso}"
    return "https://www.google.com/travel/flights?q=" + urllib.parse.quote(q)


def _estimate(dist_mi: float) -> list[dict]:
    per = round(180 + dist_mi * 0.09)
    return [
        {"carrier": "Est. nonstop", "price": per, "stops": 0,
         "depart": "—", "duration": "—", "live": False},
        {"carrier": "Est. 1-stop", "price": round(per * 0.82), "stops": 1,
         "depart": "—", "duration": "—", "live": False},
    ]


async def _scrape_google_flights(page, origin: str, dest: str, date_iso: str) -> list[dict]:
    await page.goto(google_flights_link(origin, dest, date_iso), wait_until="networkidle")
    # NOTE: Google Flights DOM is obfuscated and changes often. Selectors below
    # are illustrative — expect to tune them. Consider Amadeus for stability.
    cards = await page.query_selector_all('[role="listitem"]')
    out = []
    for c in cards[:5]:
        try:
            price_el = await c.query_selector('[aria-label*="US dollars"]')
            price_txt = await price_el.get_attribute("aria-label") if price_el else ""
            digits = "".join(ch for ch in price_txt if ch.isdigit())
            if digits:
                out.append({"carrier": "Scraped", "price": float(digits),
                            "stops": 0, "depart": "—", "duration": "—", "live": True})
        except Exception:
            continue
    return out


async def fetch(origin_city: str, dest_city: str, date_iso: str,
                dist_mi: float) -> tuple[list[dict], bool]:
    key = cache_key("flt", origin_city, dest_city, date_iso)
    cached = cache_get(key)
    if cached is not None:
        return cached, True

    link = google_flights_link(origin_city, dest_city, date_iso)

    # 1) Official API path (preferred) — implement when creds exist
    if settings.amadeus_client_id and settings.amadeus_client_secret:
        # TODO: call Amadeus Flight Offers Search; map into the row shape below.
        pass

    # 2) Scrape path
    if settings.enable_live_scraping:
        try:
            rows = await with_page(
                lambda pg: _scrape_google_flights(pg, origin_city, dest_city, date_iso))
            if rows:
                for r in rows:
                    r["booking_url"] = link
                cache_set(key, rows)
                return rows, True
        except Exception as e:  # noqa: BLE001
            print(f"[flights] scrape failed: {e}")

    # 3) Estimate fallback
    rows = _estimate(dist_mi)
    for r in rows:
        r["booking_url"] = link
    return rows, False
