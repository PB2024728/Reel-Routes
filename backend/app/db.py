"""Async SQLite database layer.

Engine, ORM model, session factory, and dict-conversion helpers.
All festival data lives here instead of the static festivals.json.

Status values:
    active           — shown on the map
    pending_review   — discovered by catalog scraper, not yet human-approved
    inactive         — manually deactivated
    inactive_review  — was active, disappeared from FilmFreeway catalog
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Boolean, Float, Integer, Text, text

from .config import settings

_DB_PATH = Path(__file__).resolve().parents[1] / settings.db_path
DATABASE_URL = f"sqlite+aiosqlite:///{_DB_PATH}"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class FestivalRow(Base):
    __tablename__ = "festivals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(Text, nullable=False, default="")
    lat: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    lng: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tier: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    genres: Mapped[str] = mapped_column(Text, nullable=False, default="[]")       # JSON list
    max_runtime: Mapped[int] = mapped_column(Integer, nullable=False, default=9999)
    accept_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    base_fee: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deadlines: Mapped[str] = mapped_column(Text, nullable=False, default="[]")    # JSON list
    oscar_qual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attendees: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filmfreeway_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    airport: Mapped[str] = mapped_column(Text, nullable=False, default="")
    languages: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list; empty = accepts all
    festival_start: Mapped[str | None] = mapped_column(Text, nullable=True)   # ISO date: screening window opens
    festival_end: Mapped[str | None] = mapped_column(Text, nullable=True)     # ISO date: screening window closes

    # Lifecycle / scraping metadata
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    last_scraped_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Latest values the scraper found — stored separately so we can review before applying
    scraped_fee: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scraped_deadlines: Mapped[str | None] = mapped_column(Text, nullable=True)    # JSON


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Additive migrations — safe to re-run; errors mean the column already exists
        for stmt in [
            "ALTER TABLE festivals ADD COLUMN languages TEXT NOT NULL DEFAULT '[]'",
            "ALTER TABLE festivals ADD COLUMN festival_start TEXT",
            "ALTER TABLE festivals ADD COLUMN festival_end TEXT",
        ]:
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


def row_to_dict(row: FestivalRow) -> dict:
    """Full representation including internal fields (for admin use)."""
    return {
        "id": row.id,
        "name": row.name,
        "city": row.city,
        "lat": row.lat,
        "lng": row.lng,
        "tier": row.tier,
        "genres": json.loads(row.genres),
        "max_runtime": row.max_runtime,
        "accept_rate": row.accept_rate,
        "base_fee": row.base_fee,
        "deadlines": json.loads(row.deadlines),
        "oscar_qual": row.oscar_qual,
        "attendees": row.attendees,
        "filmfreeway_url": row.filmfreeway_url,
        "airport": row.airport,
        "languages": json.loads(row.languages),
        "festival_start": row.festival_start,
        "festival_end": row.festival_end,
        "status": row.status,
        "last_scraped_at": row.last_scraped_at,
        "scraped_fee": row.scraped_fee,
        "scraped_deadlines": (
            json.loads(row.scraped_deadlines) if row.scraped_deadlines else None
        ),
    }


def row_to_public_dict(row: FestivalRow) -> dict:
    """Strips internal fields — safe to return to the frontend."""
    d = row_to_dict(row)
    for k in ("status", "last_scraped_at", "scraped_fee", "scraped_deadlines"):
        d.pop(k, None)
    return d
