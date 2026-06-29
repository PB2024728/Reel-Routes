"""Reel Routes API — FastAPI backend.

Run:  uvicorn app.main:app --reload --port 8000
Docs: http://127.0.0.1:8000/docs
"""
from __future__ import annotations
import datetime as dt
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from . import geocode, scheduler
from .db import FestivalRow, init_db, get_session, row_to_dict, row_to_public_dict
from .scrapers.base import haversine_mi
from .scrapers import flights, hotels, transport, filmfreeway


# ── Startup / shutdown ────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(title="Reel Routes API", version="2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_festival_or_404(fid: int, session: AsyncSession) -> FestivalRow:
    row = (
        await session.execute(select(FestivalRow).where(FestivalRow.id == fid))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="festival not found")
    return row


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health(session: AsyncSession = Depends(get_session)):
    total = len((await session.execute(select(FestivalRow))).scalars().all())
    active = len(
        (
            await session.execute(
                select(FestivalRow).where(FestivalRow.status == "active")
            )
        ).scalars().all()
    )
    return {
        "ok": True,
        "live_scraping": settings.enable_live_scraping,
        "festivals_total": total,
        "festivals_active": active,
    }


# ── Location autocomplete ─────────────────────────────────────────────────────

@app.get("/api/geocode")
async def geocode_suggest(q: str = Query(..., min_length=3), limit: int = 6):
    return await geocode.suggest(q, limit)


# ── Festival search ───────────────────────────────────────────────────────────

@app.get("/api/festivals")
async def search_festivals(
    lat: float,
    lng: float,
    radius_mi: float = 600,
    genres: str = "",
    runtime: int = 15,
    fee_budget: int = 100,
    date_from: str = "2026-07-01",
    date_to: str = "2027-06-30",
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(
            select(FestivalRow).where(FestivalRow.status == "active")
        )
    ).scalars().all()

    sel = {g.strip() for g in genres.split(",") if g.strip()}
    d_from = dt.date.fromisoformat(date_from)
    d_to = dt.date.fromisoformat(date_to)
    out = []

    for row in rows:
        f = row_to_public_dict(row)
        dist = haversine_mi(lat, lng, f["lat"], f["lng"])
        genre_hit = bool(sel & set(f["genres"])) if sel else True
        in_window = any(
            d_from <= dt.date.fromisoformat(d["date"]) <= d_to
            for d in f["deadlines"]
        )
        runtime_ok = runtime <= f["max_runtime"]
        fee_ok = f["base_fee"] <= fee_budget
        if not (dist <= radius_mi and genre_hit and in_window):
            continue
        fit = (
            35 * genre_hit
            + 25 * in_window
            + 20 * (dist <= radius_mi)
            + 10 * runtime_ok
            + 10 * fee_ok
        )
        out.append({**f, "dist_mi": round(dist, 1), "fit": int(fit)})

    out.sort(key=lambda x: (-x["fit"], x["dist_mi"]))
    return out


# ── Live festival detail refresh (FilmFreeway) ────────────────────────────────

@app.get("/api/festivals/{fid}/refresh")
async def refresh_festival(
    fid: int, session: AsyncSession = Depends(get_session)
):
    row = await _get_festival_or_404(fid, session)
    data, live = await filmfreeway.refresh_festival(row.filmfreeway_url)
    return {"live": live, "scraped": data, "festival": row_to_public_dict(row)}


# ── Travel ────────────────────────────────────────────────────────────────────

@app.get("/api/flights")
async def get_flights(
    origin: str,
    fid: int,
    date: str,
    dist_mi: float = 0,
    session: AsyncSession = Depends(get_session),
):
    row = await _get_festival_or_404(fid, session)
    rows, live = await flights.fetch(origin, row.city, date, dist_mi)
    return {"live": live, "offers": rows}


@app.get("/api/hotels")
async def get_hotels(
    fid: int,
    radius_mi: float = 5,
    checkin: str = "2026-08-20",
    nights: int = 3,
    rooms: int = 2,
    session: AsyncSession = Depends(get_session),
):
    row = await _get_festival_or_404(fid, session)
    rows, live = await hotels.fetch(
        row.city, row.lat, row.lng, radius_mi, checkin, nights, rooms
    )
    return {"live": live, "hotels": rows}


@app.get("/api/cars")
async def get_cars(
    fid: int,
    pickup: str = "2026-08-20",
    dropoff: str = "2026-08-23",
    session: AsyncSession = Depends(get_session),
):
    row = await _get_festival_or_404(fid, session)
    rows, live = await transport.fetch_cars(row.airport, pickup, dropoff)
    return {"live": live, "cars": rows}


@app.get("/api/rideshare")
async def get_rideshare(
    plat: float,
    plng: float,
    fid: int,
    session: AsyncSession = Depends(get_session),
):
    row = await _get_festival_or_404(fid, session)
    return {
        "estimates": transport.rideshare_estimates(
            plat, plng, row.lat, row.lng, row.name
        )
    }


# ── Admin ─────────────────────────────────────────────────────────────────────
# No auth yet — add an API-key middleware before exposing these to the internet.

@app.get("/api/admin/festivals")
async def admin_list_festivals(
    status: str = "",
    session: AsyncSession = Depends(get_session),
):
    """List all festivals, optionally filtered by status."""
    q = select(FestivalRow)
    if status:
        q = q.where(FestivalRow.status == status)
    rows = (await session.execute(q.order_by(FestivalRow.status, FestivalRow.name))).scalars().all()
    return [row_to_dict(row) for row in rows]


@app.post("/api/admin/festivals/{fid}/approve")
async def admin_approve_festival(
    fid: int, session: AsyncSession = Depends(get_session)
):
    """Approve a pending_review festival — sets status to active."""
    row = await _get_festival_or_404(fid, session)
    row.status = "active"
    await session.commit()
    return {"ok": True, "festival": row_to_dict(row)}


@app.post("/api/admin/festivals/{fid}/deactivate")
async def admin_deactivate_festival(
    fid: int, session: AsyncSession = Depends(get_session)
):
    """Deactivate a festival — sets status to inactive."""
    row = await _get_festival_or_404(fid, session)
    row.status = "inactive"
    await session.commit()
    return {"ok": True, "festival": row_to_dict(row)}


@app.post("/api/admin/festivals/{fid}/reactivate")
async def admin_reactivate_festival(
    fid: int, session: AsyncSession = Depends(get_session)
):
    """Re-activate a previously inactive or inactive_review festival."""
    row = await _get_festival_or_404(fid, session)
    row.status = "active"
    await session.commit()
    return {"ok": True, "festival": row_to_dict(row)}


@app.post("/api/admin/festivals")
async def admin_add_festival(
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Manually add a festival. Provide at minimum: name, city, lat, lng, filmfreeway_url."""
    import json as _json

    row = FestivalRow(
        name=body.get("name", ""),
        city=body.get("city", ""),
        lat=float(body.get("lat", 0)),
        lng=float(body.get("lng", 0)),
        tier=int(body.get("tier", 3)),
        genres=_json.dumps(body.get("genres", [])),
        max_runtime=int(body.get("max_runtime", 9999)),
        accept_rate=float(body.get("accept_rate", 0)),
        base_fee=int(body.get("base_fee", 0)),
        deadlines=_json.dumps(body.get("deadlines", [])),
        oscar_qual=bool(body.get("oscar_qual", False)),
        attendees=int(body.get("attendees", 0)),
        filmfreeway_url=body.get("filmfreeway_url", ""),
        airport=body.get("airport", ""),
        status=body.get("status", "active"),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return {"ok": True, "festival": row_to_dict(row)}


@app.post("/api/admin/sync")
async def admin_trigger_sync(background_tasks: BackgroundTasks):
    """Kick off a catalog sync in the background and return immediately."""
    async def _run():
        from .scrapers import catalog
        async with AsyncSessionLocal() as s:  # type: ignore[name-defined]
            await catalog.sync_catalog(s)

    # Import here to avoid circular — AsyncSessionLocal is already exported from db
    from .db import AsyncSessionLocal
    background_tasks.add_task(_run)
    return {"ok": True, "message": "catalog sync started in background"}


# ── Frontend ──────────────────────────────────────────────────────────────────

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
if FRONTEND.exists():
    app.mount("/app", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")

    @app.get("/")
    def root():
        return FileResponse(str(FRONTEND / "index.html"))
