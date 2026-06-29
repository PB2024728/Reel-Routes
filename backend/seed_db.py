#!/usr/bin/env python
"""One-time migration: load festivals.json into the SQLite database.

Run from the backend/ directory:
    python seed_db.py

Safe to re-run — existing rows are skipped (matched by filmfreeway_url).
"""
from __future__ import annotations
import asyncio
import json
import sys
from pathlib import Path

# Make sure 'app' is importable when running as a script
sys.path.insert(0, str(Path(__file__).parent))

from app.db import AsyncSessionLocal, FestivalRow, init_db  # noqa: E402
from sqlalchemy import select  # noqa: E402


async def seed() -> None:
    data_path = Path(__file__).parent / "app" / "data" / "festivals.json"
    if not data_path.exists():
        print(f"ERROR: {data_path} not found")
        sys.exit(1)

    festivals = json.loads(data_path.read_text(encoding="utf-8"))
    print(f"Found {len(festivals)} festivals in JSON.")

    await init_db()

    async with AsyncSessionLocal() as session:
        # Build lookup of existing rows by filmfreeway_url
        existing_urls: set[str] = {
            row.filmfreeway_url
            for row in (await session.execute(select(FestivalRow))).scalars().all()
        }

        added = skipped = 0
        for f in festivals:
            url = f.get("filmfreeway_url", "")
            if url and url in existing_urls:
                skipped += 1
                continue

            row = FestivalRow(
                name=f["name"],
                city=f["city"],
                lat=f["lat"],
                lng=f["lng"],
                tier=f.get("tier", 3),
                genres=json.dumps(f.get("genres", [])),
                max_runtime=f.get("max_runtime", 9999),
                accept_rate=f.get("accept_rate", 0.0),
                base_fee=f.get("base_fee", 0),
                deadlines=json.dumps(
                    [{"label": d["label"], "date": d["date"]} for d in f.get("deadlines", [])]
                ),
                oscar_qual=f.get("oscar_qual", False),
                attendees=f.get("attendees", 0),
                filmfreeway_url=url,
                airport=f.get("airport", ""),
                status="active",
            )
            session.add(row)
            added += 1

        await session.commit()

    print(f"Done. Added: {added}  Skipped (already exist): {skipped}")


if __name__ == "__main__":
    asyncio.run(seed())
