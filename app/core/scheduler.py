import logging
from datetime import datetime, timezone

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.services.nflverse_sync import sync_all_if_stale

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(executors={"default": ThreadPoolExecutor(2)})


def start_scheduler() -> None:
    scheduler.add_job(
        sync_all_if_stale,
        trigger=IntervalTrigger(hours=settings.nflverse_refresh_interval_hours),
        id="nflverse_sync",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info("Scheduler started")

    # Fire an immediate one-shot check on startup
    scheduler.add_job(
        sync_all_if_stale,
        trigger="date",
        run_date=datetime.now(timezone.utc),
        id="nflverse_sync_startup",
        replace_existing=True,
        max_instances=1,
    )


def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
