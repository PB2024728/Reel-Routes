"""Reel Routes API — FastAPI backend.

Run:  uvicorn app.main:app --reload --port 8000
Docs: http://127.0.0.1:8000/docs
"""
from __future__ import annotations
import json
import datetime as dt
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import settings
from . import geocode
from .scrapers.base import haversine_mi
from .scrapers import flights, hotels, transport, filmfreeway

app = FastAPI(title="Reel Routes API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"], allow_headers=["*"],
)

DATA = Path(__file__).parent / "data" / "festivals.json"
FESTIVALS = json.loads(DATA.read_text())


# ---------------- Health ----------------
@app.get("/api/health")
def health():
    return {"ok": True, "live_scraping": settings.enable_live_scraping,
            "festivals": len(FESTIVALS)}


# ---------------- Location autocomplete ----------------
@app.get("/api/geocode")
async def geocode_suggest(q: str = Query(..., min_length=3), limit: int = 6):
    return await geocode.suggest(q, limit)


# ---------------- Festival search ----------------
@app.get("/api/festivals")
def search_festivals(
    lat: float, lng: float,
    radius_mi: float = 600,
    genres: str = "",
    runtime: int = 15,
    fee_budget: int = 100,
    date_from: str = "2026-07-01",
    date_to: str = "2027-06-30",
):
    sel = {g.strip() for g in genres.split(",") if g.strip()}
    d_from = dt.date.fromisoformat(date_from)
    d_to = dt.date.fromisoformat(date_to)
    out = []
    for f in FESTIVALS:
        dist = haversine_mi(lat, lng, f["lat"], f["lng"])
        genre_hit = bool(sel & set(f["genres"])) if sel else True
        in_window = any(d_from <= dt.date.fromisoformat(d["date"]) <= d_to
                        for d in f["deadlines"])
        runtime_ok = runtime <= f["max_runtime"]
        fee_ok = f["base_fee"] <= fee_budget
        if not (dist <= radius_mi and genre_hit and in_window):
            continue
        fit = (35 * genre_hit + 25 * in_window + 20 * (dist <= radius_mi)
               + 10 * runtime_ok + 10 * fee_ok)
        out.append({**f, "dist_mi": round(dist, 1), "fit": int(fit)})
    out.sort(key=lambda x: (-x["fit"], x["dist_mi"]))
    return out


# ---------------- Live festival detail refresh (FilmFreeway) ----------------
@app.get("/api/festivals/{fid}/refresh")
async def refresh_festival(fid: int):
    f = next((x for x in FESTIVALS if x["id"] == fid), None)
    if not f:
        return {"error": "not found"}
    data, live = await filmfreeway.refresh_festival(f["filmfreeway_url"])
    return {"live": live, "scraped": data, "festival": f}


# ---------------- Travel ----------------
@app.get("/api/flights")
async def get_flights(origin: str, fid: int, date: str, dist_mi: float = 0):
    f = next((x for x in FESTIVALS if x["id"] == fid), None)
    if not f:
        return {"error": "not found"}
    rows, live = await flights.fetch(origin, f["city"], date, dist_mi)
    return {"live": live, "offers": rows}


@app.get("/api/hotels")
async def get_hotels(fid: int, radius_mi: float = 5, checkin: str = "2026-08-20",
                     nights: int = 3, rooms: int = 2):
    f = next((x for x in FESTIVALS if x["id"] == fid), None)
    if not f:
        return {"error": "not found"}
    rows, live = await hotels.fetch(f["city"], f["lat"], f["lng"], radius_mi,
                                    checkin, nights, rooms)
    return {"live": live, "hotels": rows}


@app.get("/api/cars")
async def get_cars(fid: int, pickup: str = "2026-08-20", dropoff: str = "2026-08-23"):
    f = next((x for x in FESTIVALS if x["id"] == fid), None)
    if not f:
        return {"error": "not found"}
    rows, live = await transport.fetch_cars(f["airport"], pickup, dropoff)
    return {"live": live, "cars": rows}


@app.get("/api/rideshare")
def get_rideshare(plat: float, plng: float, fid: int):
    f = next((x for x in FESTIVALS if x["id"] == fid), None)
    if not f:
        return {"error": "not found"}
    return {"estimates": transport.rideshare_estimates(plat, plng, f["lat"],
            f["lng"], f["name"])}


# ---------------- Serve frontend (so one server runs the whole app) ----------------
FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
if FRONTEND.exists():
    app.mount("/app", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")

    @app.get("/")
    def root():
        return FileResponse(str(FRONTEND / "index.html"))
