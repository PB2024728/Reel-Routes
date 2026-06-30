"""Contract tests — every /api/* route returns the documented shape.

These tests verify that each endpoint:
  - Returns a 2xx status for valid inputs
  - Returns 404 for unknown festival IDs
  - Returns 422 for missing required params
  - Includes all documented top-level keys with the right types
"""
from unittest.mock import AsyncMock, patch

import pytest

# Keys every public festival dict must contain
_FESTIVAL_PUBLIC = {
    "id", "name", "city", "lat", "lng", "tier", "genres", "max_runtime",
    "accept_rate", "base_fee", "deadlines", "oscar_qual", "attendees",
    "filmfreeway_url", "airport", "languages", "festival_start", "festival_end",
}
# Admin view adds internal tracking fields
_FESTIVAL_ADMIN = _FESTIVAL_PUBLIC | {
    "status", "last_scraped_at", "scraped_fee", "scraped_deadlines",
}


# ---------------------------------------------------------------------------
# /api/health
# ---------------------------------------------------------------------------

class TestHealth:
    async def test_shape(self, client_and_fid):
        client, _ = client_and_fid
        r = await client.get("/api/health")
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d["ok"], bool)
        assert isinstance(d["live_scraping"], bool)
        assert isinstance(d["festivals_total"], int)
        assert isinstance(d["festivals_active"], int)


# ---------------------------------------------------------------------------
# /api/geocode
# ---------------------------------------------------------------------------

class TestGeocode:
    async def test_shape(self, client_and_fid):
        client, _ = client_and_fid
        fake = [{"label": "Atlanta, GA", "secondary": "Georgia, USA",
                 "lat": 33.749, "lng": -84.388}]
        with patch("app.geocode.suggest", new=AsyncMock(return_value=fake)):
            r = await client.get("/api/geocode?q=Atlanta")
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        item = items[0]
        assert {"label", "secondary", "lat", "lng"} <= item.keys()
        assert isinstance(item["lat"], (int, float))
        assert isinstance(item["lng"], (int, float))

    async def test_too_short_returns_422(self, client_and_fid):
        client, _ = client_and_fid
        r = await client.get("/api/geocode?q=ab")
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# /api/festivals
# ---------------------------------------------------------------------------

class TestFestivals:
    async def test_shape(self, client_and_fid):
        client, _ = client_and_fid
        r = await client.get(
            "/api/festivals?lat=40.0&lng=-111.0&radius_mi=5000"
            "&date_from=2026-01-01&date_to=2028-12-31&fee_budget=500"
        )
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert len(items) >= 1
        f = items[0]
        assert _FESTIVAL_PUBLIC <= f.keys()
        assert "dist_mi" in f and "fit" in f
        assert isinstance(f["genres"], list)
        assert isinstance(f["deadlines"], list)
        assert isinstance(f["fit"], int)
        assert 0 <= f["fit"] <= 100

    async def test_missing_lat_lng_returns_422(self, client_and_fid):
        client, _ = client_and_fid
        r = await client.get("/api/festivals")
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# /api/festivals/{fid}/refresh
# ---------------------------------------------------------------------------

class TestFestivalRefresh:
    async def test_shape(self, client_and_fid):
        client, fid = client_and_fid
        with patch("app.main.filmfreeway.refresh_festival",
                   new=AsyncMock(return_value=(None, False))):
            r = await client.get(f"/api/festivals/{fid}/refresh")
        assert r.status_code == 200
        d = r.json()
        assert "live" in d and "scraped" in d and "festival" in d
        assert isinstance(d["live"], bool)
        assert _FESTIVAL_PUBLIC <= d["festival"].keys()

    async def test_unknown_fid_returns_404(self, client_and_fid):
        client, _ = client_and_fid
        r = await client.get("/api/festivals/99999/refresh")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# /api/flights
# ---------------------------------------------------------------------------

class TestFlights:
    async def test_shape(self, client_and_fid):
        client, fid = client_and_fid
        r = await client.get(
            f"/api/flights?origin=New+York&fid={fid}"
            f"&date=2027-09-15&origin_lat=40.7128&origin_lng=-74.006"
        )
        assert r.status_code == 200
        d = r.json()
        assert "live" in d
        assert isinstance(d["live"], bool)
        assert isinstance(d["offers"], list)
        for offer in d["offers"]:
            assert {"carrier", "price", "stops", "depart",
                    "duration", "live", "booking_url"} <= offer.keys()
            assert isinstance(offer["price"], (int, float))
            assert isinstance(offer["stops"], int)

    async def test_unknown_fid_returns_404(self, client_and_fid):
        client, _ = client_and_fid
        r = await client.get("/api/flights?origin=NYC&fid=99999&date=2027-09-15")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# /api/hotels
# ---------------------------------------------------------------------------

class TestHotels:
    async def test_shape(self, client_and_fid):
        client, fid = client_and_fid
        r = await client.get(
            f"/api/hotels?fid={fid}&radius_mi=5&checkin=2027-09-15&nights=3&rooms=1"
        )
        assert r.status_code == 200
        d = r.json()
        assert "live" in d
        assert isinstance(d["live"], bool)
        assert isinstance(d["hotels"], list)
        for h in d["hotels"]:
            assert {"name", "nightly", "booking_url"} <= h.keys()
            assert isinstance(h["nightly"], (int, float))

    async def test_unknown_fid_returns_404(self, client_and_fid):
        client, _ = client_and_fid
        r = await client.get("/api/hotels?fid=99999")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# /api/cars
# ---------------------------------------------------------------------------

class TestCars:
    async def test_shape(self, client_and_fid):
        client, fid = client_and_fid
        r = await client.get(
            f"/api/cars?fid={fid}&pickup=2027-09-15&dropoff=2027-09-18"
        )
        assert r.status_code == 200
        d = r.json()
        assert "live" in d
        assert isinstance(d["live"], bool)
        assert isinstance(d["cars"], list)
        for c in d["cars"]:
            assert {"car_class", "daily", "booking_url"} <= c.keys()
            assert isinstance(c["daily"], (int, float))

    async def test_unknown_fid_returns_404(self, client_and_fid):
        client, _ = client_and_fid
        r = await client.get("/api/cars?fid=99999")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# /api/rideshare
# ---------------------------------------------------------------------------

class TestRideshare:
    async def test_shape(self, client_and_fid):
        client, fid = client_and_fid
        r = await client.get(
            f"/api/rideshare?plat=40.7128&plng=-74.006&fid={fid}"
        )
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d["estimates"], list)
        assert len(d["estimates"]) == 2
        for e in d["estimates"]:
            assert {"service", "est_low", "est_high",
                    "distance_mi", "deeplink", "note"} <= e.keys()
            assert e["est_low"] <= e["est_high"]

    async def test_unknown_fid_returns_404(self, client_and_fid):
        client, _ = client_and_fid
        r = await client.get("/api/rideshare?plat=0&plng=0&fid=99999")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# /api/admin/*
# ---------------------------------------------------------------------------

class TestAdmin:
    async def test_list_shape(self, client_and_fid):
        client, _ = client_and_fid
        r = await client.get("/api/admin/festivals")
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list) and len(rows) >= 1
        assert _FESTIVAL_ADMIN <= rows[0].keys()

    async def test_add_festival(self, client_and_fid):
        client, _ = client_and_fid
        r = await client.post("/api/admin/festivals", json={
            "name": "Contract Test Fest", "city": "Austin, TX",
            "lat": 30.267, "lng": -97.743,
            "filmfreeway_url": "https://filmfreeway.com/contracttest",
            "airport": "AUS",
        })
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert _FESTIVAL_ADMIN <= d["festival"].keys()
        assert d["festival"]["name"] == "Contract Test Fest"

    async def test_approve_deactivate_reactivate(self, client_and_fid):
        client, _ = client_and_fid
        r = await client.post("/api/admin/festivals", json={
            "name": "Lifecycle Fest", "city": "Denver, CO",
            "lat": 39.742, "lng": -104.987,
            "filmfreeway_url": "https://filmfreeway.com/lifecyclefest",
            "airport": "DEN", "status": "pending_review",
        })
        new_fid = r.json()["festival"]["id"]

        r = await client.post(f"/api/admin/festivals/{new_fid}/approve")
        assert r.status_code == 200
        assert r.json()["festival"]["status"] == "active"

        r = await client.post(f"/api/admin/festivals/{new_fid}/deactivate")
        assert r.status_code == 200
        assert r.json()["festival"]["status"] == "inactive"

        r = await client.post(f"/api/admin/festivals/{new_fid}/reactivate")
        assert r.status_code == 200
        assert r.json()["festival"]["status"] == "active"

    async def test_field_refresh_shape(self, client_and_fid):
        client, _ = client_and_fid
        r = await client.post("/api/admin/field-refresh")
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert isinstance(d["message"], str)

    async def test_sync_shape(self, client_and_fid):
        client, _ = client_and_fid
        r = await client.post("/api/admin/sync")
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert isinstance(d["message"], str)
