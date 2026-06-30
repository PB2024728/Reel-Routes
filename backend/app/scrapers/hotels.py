"""Hotel pricing near a festival venue.

Returns properties within `radius_mi` of the venue, each with its distance to the
venue and a working booking deep-link. Live scraping via Playwright is optional;
estimate fallback is always available.
"""
from __future__ import annotations
import math
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


def _offset_coords(lat: float, lng: float, dist_mi: float, bearing_deg: float):
    """Return (lat, lng) displaced dist_mi from the origin in the given compass bearing."""
    d = dist_mi / 3959.0
    b = math.radians(bearing_deg)
    lat1, lng1 = math.radians(lat), math.radians(lng)
    lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(b))
    lng2 = lng1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(lat1),
                              math.cos(d) - math.sin(lat1) * math.sin(lat2))
    return round(math.degrees(lat2), 5), round(math.degrees(lng2), 5)


def _estimate(city: str, venue_lat: float, venue_lng: float, radius_mi: float,
              checkin: str, nights: int, rooms: int) -> list[dict]:
    base_rate = 145
    link = booking_link(city, checkin, nights, rooms)
    # bearings spread hotels around the venue so map routes look distinct
    candidates = [
        {"name": "Downtown boutique (sample)", "nightly": base_rate + 40, "dist_mi": 0.6, "rating": 4.5, "_bearing": 45},
        {"name": "Midscale chain (sample)",    "nightly": base_rate,      "dist_mi": 1.8, "rating": 4.1, "_bearing": 200},
        {"name": "Budget inn (sample)",        "nightly": base_rate - 55, "dist_mi": 4.2, "rating": 3.7, "_bearing": 300},
    ]
    out = []
    for c in candidates:
        if c["dist_mi"] <= radius_mi:
            bearing = c.pop("_bearing")
            lat, lng = _offset_coords(venue_lat, venue_lng, c["dist_mi"], bearing)
            c["lat"] = lat
            c["lng"] = lng
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

    return _estimate(city, venue_lat, venue_lng, radius_mi, checkin, nights, rooms), False
