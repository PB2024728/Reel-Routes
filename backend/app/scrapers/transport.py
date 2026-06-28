"""Ground transport: car rentals (scrapeable) + rideshare (deep-links only).

Rideshare: Uber/Lyft do NOT expose reliable public fare quotes. We compute a
transparent distance-based estimate and return official deep-links that open the
apps with pickup/dropoff pre-filled. Swap in the official Uber API later if you
obtain access.
"""
from __future__ import annotations
import urllib.parse

from .base import cache_key, cache_get, cache_set, with_page, haversine_mi
from ..config import settings


# ---------------- Car rentals ----------------
def kayak_cars_link(airport: str, pickup: str, dropoff: str) -> str:
    return f"https://www.kayak.com/cars/{airport}/{pickup}/{dropoff}"


def _car_estimate(airport: str, pickup: str, dropoff: str) -> list[dict]:
    link = kayak_cars_link(airport, pickup, dropoff)
    return [
        {"vendor": "Economy (sample)", "car_class": "Economy", "daily": 42,
         "booking_url": link, "live": False},
        {"vendor": "SUV (sample)", "car_class": "SUV", "daily": 78,
         "booking_url": link, "live": False},
        {"vendor": "Passenger van (sample)", "car_class": "Van (7+ seats)",
         "daily": 119, "booking_url": link, "live": False},
    ]


async def fetch_cars(airport: str, pickup: str, dropoff: str) -> tuple[list[dict], bool]:
    key = cache_key("car", airport, pickup, dropoff)
    cached = cache_get(key)
    if cached is not None:
        return cached, True
    # Live scrape path could target Kayak/Expedia here; estimate for now.
    return _car_estimate(airport, pickup, dropoff), False


# ---------------- Rideshare (deep-links + estimate) ----------------
def uber_deeplink(plat: float, plng: float, dlat: float, dlng: float,
                  dnick: str = "Festival") -> str:
    params = {
        "action": "setPickup", "pickup": "my_location",
        "dropoff[latitude]": dlat, "dropoff[longitude]": dlng,
        "dropoff[nickname]": dnick,
    }
    return "https://m.uber.com/ul/?" + urllib.parse.urlencode(params)


def lyft_deeplink(dlat: float, dlng: float) -> str:
    params = {"id": "lyft", "destination[latitude]": dlat,
              "destination[longitude]": dlng}
    return "https://lyft.com/ride?" + urllib.parse.urlencode(params)


def rideshare_estimates(plat, plng, dlat, dlng, dest_nick="Festival") -> list[dict]:
    dist = haversine_mi(plat, plng, dlat, dlng)
    # transparent model: base + per-mile band (varies by city/surge)
    uber_low = round(3.5 + dist * 1.4, 2)
    uber_high = round(5.0 + dist * 2.3, 2)
    lyft_low = round(3.0 + dist * 1.45, 2)
    lyft_high = round(4.8 + dist * 2.4, 2)
    return [
        {"service": "Uber", "est_low": uber_low, "est_high": uber_high,
         "distance_mi": round(dist, 1), "deeplink": uber_deeplink(plat, plng, dlat, dlng, dest_nick),
         "note": "Estimate; live fare varies with surge. Opens Uber pre-filled."},
        {"service": "Lyft", "est_low": lyft_low, "est_high": lyft_high,
         "distance_mi": round(dist, 1), "deeplink": lyft_deeplink(dlat, dlng),
         "note": "Estimate; live fare varies with surge. Opens Lyft pre-filled."},
    ]
