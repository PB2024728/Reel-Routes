"""Location autocomplete — accepts a ZIP or 'City, State' and returns suggestions,
Yelp/Fandango-style. Uses free OpenStreetMap Nominatim (no key required).

Per Nominatim usage policy: send a valid identifying email, cache results, and
keep request volume modest. For production scale, self-host Nominatim or use a
paid geocoder.
"""
from __future__ import annotations
import httpx

from .scrapers.base import cache_key, cache_get, cache_set
from .config import settings


def _looks_like_zip(q: str) -> bool:
    q = q.strip()
    return q.isdigit() and len(q) == 5


async def suggest(query: str, limit: int = 6) -> list[dict]:
    query = query.strip()
    if len(query) < 3:
        return []

    key = cache_key("geo", query.lower(), limit)
    cached = cache_get(key)
    if cached is not None:
        return cached

    params = {
        "format": "json",
        "addressdetails": 1,
        "limit": limit,
        "countrycodes": "us",
        "email": settings.nominatim_email,
    }
    if _looks_like_zip(query):
        params["postalcode"] = query
    else:
        params["q"] = query

    headers = {"User-Agent": f"ReelRoutes/1.0 ({settings.nominatim_email})"}
    url = settings.nominatim_url + "/search"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, params=params, headers=headers)
            r.raise_for_status()
            data = r.json()
    except Exception as e:  # noqa: BLE001
        print(f"[geocode] lookup failed: {e}")
        return []

    out = []
    for d in data:
        addr = d.get("address", {})
        city = (addr.get("city") or addr.get("town") or addr.get("village")
                or addr.get("hamlet") or addr.get("county") or "")
        state = addr.get("state", "")
        postcode = addr.get("postcode", "")
        kind = "zip" if _looks_like_zip(query) else (
            "city" if city else "address")
        # Build a clean Yelp-style primary label
        if city and state:
            label = f"{city}, {_abbr(state)}"
            if postcode:
                label += f" {postcode}"
        else:
            label = d.get("display_name", "").split(",")[0]
        out.append({
            "label": label,
            "secondary": d.get("display_name", ""),
            "lat": float(d["lat"]),
            "lng": float(d["lon"]),
            "kind": kind,
        })

    cache_set(key, out)
    return out


_STATE_ABBR = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI",
    "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX",
    "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
    "District of Columbia": "DC",
}


def _abbr(state: str) -> str:
    return _STATE_ABBR.get(state, state)
