"""Background scheduler.

Two recurring jobs:
  catalog_sync   — weekly (Sunday 03:00 UTC)
                   Crawls FilmFreeway browse page; new festivals → pending_review,
                   vanished active festivals → inactive_review.

  field_refresh  — daily (04:00 UTC)
                   For every active festival, re-scrapes FilmFreeway to pull
                   the latest deadlines and entry fee into the DB.

Both jobs are no-ops when ENABLE_LIVE_SCRAPING=False.
Both jobs are skipped (logged, not crashed) when their respective config flag is off.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import settings
from .db import AsyncSessionLocal

log = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None


async def _job_catalog_sync() -> None:
    if not settings.catalog_sync_enabled:
        return
    from .scrapers import catalog
    async with AsyncSessionLocal() as session:
        result = await catalog.sync_catalog(session)
        log.info("[scheduler] catalog sync complete: %s", result)


async def _job_field_refresh() -> None:
    if not settings.field_refresh_enabled:
        return
    if not settings.enable_live_scraping:
        return

    from sqlalchemy import select
    from .db import FestivalRow
    from .scrapers import filmfreeway

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(FestivalRow).where(FestivalRow.status == "active")
            )
        ).scalars().all()

        refreshed = errors = 0
        for row in rows:
            if not row.filmfreeway_url:
                continue
            data, live = await filmfreeway.refresh_festival(row.filmfreeway_url)
            if not (live and data):
                errors += 1
                continue
            if data.get("base_fee") is not None:
                row.scraped_fee = data["base_fee"]
                row.base_fee = data["base_fee"]
            if data.get("deadlines_raw"):
                row.scraped_deadlines = json.dumps(data["deadlines_raw"])
            row.last_scraped_at = datetime.now(timezone.utc).isoformat()
            refreshed += 1

        await session.commit()
        log.info(
            "[scheduler] field refresh: %d/%d updated, %d errors",
            refreshed, len(rows), errors,
        )


def start() -> None:
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(_job_catalog_sync, CronTrigger(day_of_week="sun", hour=3, minute=0))
    _scheduler.add_job(_job_field_refresh, CronTrigger(hour=4, minute=0))
    _scheduler.start()
    log.info(
        "[scheduler] started — catalog sync Sun 03:00 UTC, field refresh daily 04:00 UTC"
    )


def stop() -> None:
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("[scheduler] stopped")
