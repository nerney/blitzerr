import logging
from datetime import datetime, timezone

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import NFLVERSE_REFRESH_HOURS
from app.services.nflverse_sync import sync_all_if_stale
from app.services.prowlarr import check_health as prowlarr_health, PROWLARR_HEALTH_INTERVAL_HOURS
from app.services.qbittorrent import check_health as qbittorrent_health, QBITTORRENT_CHECK_INTERVAL_SECONDS
from app.services.sabnzbd import check_health as sabnzbd_health, SABNZBD_CHECK_INTERVAL_SECONDS

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(executors={"default": ThreadPoolExecutor(4)})


def start_scheduler() -> None:
    now = datetime.now(timezone.utc)

    scheduler.add_job(
        sync_all_if_stale,
        trigger=IntervalTrigger(hours=NFLVERSE_REFRESH_HOURS),
        id="nflverse_sync",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        sync_all_if_stale,
        trigger="date",
        run_date=now,
        id="nflverse_sync_startup",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        prowlarr_health,
        trigger=IntervalTrigger(hours=PROWLARR_HEALTH_INTERVAL_HOURS),
        id="prowlarr_health",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=600,
    )
    scheduler.add_job(
        prowlarr_health,
        trigger="date",
        run_date=now,
        id="prowlarr_health_startup",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        qbittorrent_health,
        trigger=IntervalTrigger(seconds=QBITTORRENT_CHECK_INTERVAL_SECONDS),
        id="qbittorrent_health",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=30,
    )
    scheduler.add_job(
        qbittorrent_health,
        trigger="date",
        run_date=now,
        id="qbittorrent_health_startup",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        sabnzbd_health,
        trigger=IntervalTrigger(seconds=SABNZBD_CHECK_INTERVAL_SECONDS),
        id="sabnzbd_health",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=30,
    )
    scheduler.add_job(
        sabnzbd_health,
        trigger="date",
        run_date=now,
        id="sabnzbd_health_startup",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
