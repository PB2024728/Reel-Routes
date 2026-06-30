"""Flight pricing.

Strategy:
  1. If SERPAPI_KEY is set, query Google Flights via Serpapi (structured, no scraping).
  2. Else if live scraping enabled, scrape a metasearch results page via Playwright.
  3. Else return a distance-based estimate.

Always returns a real Google Flights deep-link so the user can book immediately.
"""
from __future__ import annotations
import re
import urllib.parse

import httpx

from .base import cache_key, cache_get, cache_set, with_page, haversine_mi
from ..config import settings

# Major US airports with (lat, lng) — used to resolve origin city coords → IATA code
# for Serpapi, which requires IATA codes rather than city name strings.
_US_AIRPORTS: dict[str, tuple[float, float]] = {
    "ATL": (33.6407, -84.4277), "LAX": (33.9425, -118.4081), "ORD": (41.9742, -87.9073),
    "DFW": (32.8998, -97.0403), "DEN": (39.8561, -104.6737), "JFK": (40.6413, -73.7781),
    "SFO": (37.6213, -122.3790), "SEA": (47.4502, -122.3088), "LAS": (36.0840, -115.1537),
    "MCO": (28.4312, -81.3081), "EWR": (40.6895, -74.1745), "MIA": (25.7959, -80.2870),
    "PHX": (33.4373, -112.0078), "IAH": (29.9902, -95.3368), "BOS": (42.3656, -71.0096),
    "MSP": (44.8848, -93.2223), "DTW": (42.2124, -83.3534), "FLL": (26.0726, -80.1527),
    "PHL": (39.8721, -75.2408), "LGA": (40.7772, -73.8726), "CLT": (35.2140, -80.9431),
    "BWI": (39.1754, -76.6682), "SLC": (40.7899, -111.9791), "DCA": (38.8521, -77.0377),
    "SAN": (32.7336, -117.1897), "MDW": (41.7868, -87.7522), "TPA": (27.9755, -82.5332),
    "PDX": (45.5887, -122.5975), "STL": (38.7487, -90.3700), "HNL": (21.3187, -157.9224),
    "BNA": (36.1245, -86.6782), "AUS": (30.1975, -97.6664), "MEM": (35.0424, -89.9767),
    "RDU": (35.8801, -78.7880), "OAK": (37.7213, -122.2208), "MCI": (39.2976, -94.7139),
    "SMF": (38.6954, -121.5908), "PIT": (40.4915, -80.2329), "CLE": (41.4117, -81.8498),
    "IND": (39.7173, -86.2944), "CMH": (39.9980, -82.8919), "MSY": (29.9934, -90.2580),
    "SJC": (37.3626, -121.9290), "JAX": (30.4941, -81.6879), "RSW": (26.5362, -81.7552),
    "ABQ": (35.0402, -106.6090), "SAT": (29.5337, -98.4698), "BOI": (43.5644, -116.2228),
    "TUS": (32.1161, -110.9410), "OMA": (41.3032, -95.8941), "BUF": (42.9405, -78.7322),
    "BDL": (41.9389, -72.6832), "MKE": (42.9472, -87.8966), "GRR": (42.8808, -85.5228),
    "CVG": (39.0488, -84.6678), "DAL": (32.8471, -96.8517), "HOU": (29.6454, -95.2789),
    "LGB": (33.8177, -118.1516), "SNA": (33.6757, -117.8682), "OGG": (20.8986, -156.4305),
    "KOA": (19.7388, -156.0456), "LIH": (21.9760, -159.3390), "ANC": (61.1744, -149.9964),
}


def _nearest_iata(lat: float, lng: float) -> str:
    best_iata, best_dist = "ATL", float("inf")
    for iata, (alat, alng) in _US_AIRPORTS.items():
        d = haversine_mi(lat, lng, alat, alng)
        if d < best_dist:
            best_dist = d
            best_iata = iata
    return best_iata


def google_flights_link(origin_city: str, dest_airport: str, date_iso: str) -> str:
    q = f"flights from {origin_city} to {dest_airport} on {date_iso}"
    return "https://www.google.com/travel/flights?q=" + urllib.parse.quote(q)


def _estimate(dist_mi: float) -> list[dict]:
    per = round(180 + dist_mi * 0.09)
    return [
        {"carrier": "Est. nonstop", "price": per, "stops": 0,
         "depart": "—", "duration": "—", "live": False},
        {"carrier": "Est. 1-stop", "price": round(per * 0.82), "stops": 1,
         "depart": "—", "duration": "—", "live": False},
    ]


def _fmt_duration(minutes: int) -> str:
    if not minutes:
        return "—"
    h, m = divmod(minutes, 60)
    return f"{h}h {m}m" if m else f"{h}h"


async def _serpapi_fetch(
    origin_city: str, dest_airport: str, date_iso: str,
    origin_lat: float = 0.0, origin_lng: float = 0.0,
) -> list[dict]:
    departure_id = (
        _nearest_iata(origin_lat, origin_lng)
        if origin_lat and origin_lng
        else origin_city
    )
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            "https://serpapi.com/search",
            params={
                "engine": "google_flights",
                "departure_id": departure_id,
                "arrival_id": dest_airport,
                "outbound_date": date_iso,
                "currency": "USD",
                "hl": "en",
                "type": "2",  # one-way
                "api_key": settings.serpapi_key,
            },
        )
        r.raise_for_status()
        data = r.json()

    rows = []
    for group in (data.get("best_flights") or []) + (data.get("other_flights") or []):
        try:
            price = float(group["price"])
            segments = group["flights"]
            stops = len(segments) - 1
            depart = segments[0]["departure_airport"].get("time", "—")[:16]
            duration = _fmt_duration(group.get("total_duration", 0))
            carrier = segments[0].get("airline", "?")
            rows.append({
                "carrier": carrier,
                "price": price,
                "stops": stops,
                "depart": depart,
                "duration": duration,
                "live": True,
            })
        except Exception:
            continue
    return rows[:5]


async def _scrape_google_flights(page, origin: str, dest_airport: str, date_iso: str) -> list[dict]:
    await page.goto(google_flights_link(origin, dest_airport, date_iso), wait_until="networkidle")
    # NOTE: Google Flights DOM is obfuscated and changes often — expect selector maintenance.
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


async def fetch(
    origin_city: str, dest_airport: str, date_iso: str,
    dist_mi: float, origin_lat: float = 0.0, origin_lng: float = 0.0,
) -> tuple[list[dict], bool]:
    key = cache_key("flt", origin_city, dest_airport, date_iso)
    cached = cache_get(key)
    if cached is not None:
        return cached, True

    link = google_flights_link(origin_city, dest_airport, date_iso)

    # 1) Serpapi path (preferred — structured Google Flights data, no selector maintenance)
    if settings.serpapi_key:
        try:
            rows = await _serpapi_fetch(origin_city, dest_airport, date_iso, origin_lat, origin_lng)
            if rows:
                for r in rows:
                    r["booking_url"] = link
                cache_set(key, rows)
                return rows, True
        except Exception as e:  # noqa: BLE001
            print(f"[flights] Serpapi failed: {e}")

    # 2) Playwright scrape fallback
    if settings.enable_live_scraping:
        try:
            rows = await with_page(
                lambda pg: _scrape_google_flights(pg, origin_city, dest_airport, date_iso))
            if rows:
                for r in rows:
                    r["booking_url"] = link
                cache_set(key, rows)
                return rows, True
        except Exception as e:  # noqa: BLE001
            print(f"[flights] scrape failed: {e}")

    # 3) Distance-based estimate
    rows = _estimate(dist_mi)
    for r in rows:
        r["booking_url"] = link
    return rows, False
