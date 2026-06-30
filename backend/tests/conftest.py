"""Shared test fixtures.

Creates a fresh SQLite DB per session, seeds one festival, and overrides
the FastAPI get_session dependency so tests never touch the real DB.
The APScheduler is mocked out so it doesn't start background jobs.
"""
import asyncio
import json
import os
import sys
import tempfile
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


@pytest_asyncio.fixture(scope="session")
async def client_and_fid():
    from app.db import Base, FestivalRow, get_session
    from app.main import app

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    TestSession = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSession() as s:
        row = FestivalRow(
            name="Sundance Test",
            city="Park City, UT",
            lat=40.6461, lng=-111.4980, tier=1,
            genres=json.dumps(["Drama", "Documentary"]),
            max_runtime=120, accept_rate=2.5, base_fee=75,
            deadlines=json.dumps([{"label": "Regular", "date": "2027-09-15"}]),
            oscar_qual=True, attendees=50000,
            filmfreeway_url="https://filmfreeway.com/sundancetest",
            airport="SLC", languages=json.dumps([]),
            festival_start="2027-01-20", festival_end="2027-01-30",
            status="active",
        )
        s.add(row)
        await s.commit()
        await s.refresh(row)
        fid = row.id

    async def _override():
        async with TestSession() as s:
            yield s

    app.dependency_overrides[get_session] = _override

    with patch("app.scheduler.start"), patch("app.scheduler.stop"):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac, fid

    app.dependency_overrides.clear()
    await engine.dispose()
    os.unlink(db_path)
