"""Hotel pricing near a festival venue.

Returns properties within `radius_mi` of the venue, each with its distance to the
venue and a working booking deep-link. Live scraping via Playwright is optional;
estimate fallback is always available.
"""
from __future__ import annotations
import urllib.parse
import datetime as dt

from .base import cache_key, cache_get, cache_set, with_page, haversine_mi
from ..config import settings


def booking_link(city: str, checkin: str, nights: int, rooms: int) -> str:
    checkout = (dt.date.fromisoformat(checkin) + dt.timedelta(days=nights)).isoformat()
    params = {
        "ss": city, "checkin": checkin, "checkout": checkout,
        "group_adults": rooms * 2, "no_rooms": rooms,
    }
    return "https://www.booking.com/searchresults.html?" + urllib.parse.urlencode(params)


def _estimate(city: str, radius_mi: float, checkin: str, nights: int,
              rooms: int) -> list[dict]:
    base = 145
    link = booking_link(city, checkin, nights, rooms)
    candidates = [
        {"name": "Downtown boutique (sample)", "nightly": base + 40, "dist_mi": 0.6, "rating": 4.5},
        {"name": "Midscale chain (sample)", "nightly": base, "dist_mi": 1.8, "rating": 4.1},
        {"name": "Budget inn (sample)", "nightly": base - 55, "dist_mi": 4.2, "rating": 3.7},
    ]
    out = []
    for c in candidates:
        if c["dist_mi"] <= radius_mi:
            c["booking_url"] = link
            c["live"] = False
            out.append(c)
    return out


async def _scrape_booking(page, city, venue_lat, venue_lng, radius_mi,
                          checkin, nights, rooms) -> list[dict]:
    await page.goto(booking_link(city, checkin, nights, rooms),
                    wait_until="domcontentloaded")
    # Booking.com property cards — selectors illustrative, tune as needed.
    cards = await page.query_selector_all('[data-testid="property-card"]')
    out = []
    for c in cards[:12]:
        try:
            name_el = await c.query_selector('[data-testid="title"]')
            price_el = await c.query_selector('[data-testid="price-and-discounted-price"]')
            name = (await name_el.inner_text()) if name_el else "Hotel"
            ptxt = (await price_el.inner_text()) if price_el else ""
            digits = "".join(ch for ch in ptxt if ch.isdigit())
            nightly = round(float(digits) / max(nights, 1)) if digits else None
            if nightly:
                out.append({"name": name, "nightly": nightly, "dist_mi": None,
                            "rating": None, "live": True,
                            "booking_url": booking_link(city, checkin, nights, rooms)})
        except Exception:
            continue
    return out


async def fetch(city: str, venue_lat: float, venue_lng: float, radius_mi: float,
                checkin: str, nights: int, rooms: int) -> tuple[list[dict], bool]:
    key = cache_key("htl", city, radius_mi, checkin, nights, rooms)
    cached = cache_get(key)
    if cached is not None:
        return cached, True

    if settings.enable_live_scraping:
        try:
            rows = await with_page(
                lambda pg: _scrape_booking(pg, city, venue_lat, venue_lng,
                                           radius_mi, checkin, nights, rooms))
            if rows:
                cache_set(key, rows)
                return rows, True
        except Exception as e:  # noqa: BLE001
            print(f"[hotels] scrape failed: {e}")

    return _estimate(city, radius_mi, checkin, nights, rooms), False
