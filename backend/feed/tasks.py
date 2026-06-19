from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

from app.celery import app
from feed.constants import FEED_KILLMAIL_RETENTION_DAYS
from feed.helpers.clusters import detect_clusters
from feed.helpers.r2z2 import poll_r2z2_batch
from feed.models import FeedEvent, FeedKillmail
from feed.rollups.registry import build_context, run_all_rollups
from feed.rollups.writer import link_announcement_event, write_rollup_results

logger = logging.getLogger(__name__)


@app.task(queue="celery")
def poll_zkill_r2z2() -> dict:
    stats = poll_r2z2_batch()
    logger.info("R2Z2 poll complete: %s", stats)
    return stats


@app.task(queue="celery")
def detect_feed_clusters() -> int:
    count = detect_clusters(since_hours=48)
    logger.info("Detected/updated %s feed clusters", count)
    return count


@app.task(queue="celery")
def run_feed_rollups(*, since_hours: int = 48) -> int:
    now = timezone.now()
    since = now - timedelta(hours=since_hours)
    ctx = build_context(since, now)
    results = run_all_rollups(
        ctx,
        codes=["kill_burst", "fleet_active", "communication"],
    )
    written = write_rollup_results(results)
    for result in results:
        if result.source_type == "announcement" and result.source_id:
            event = FeedEvent.objects.get(
                rollup_code=result.rollup_code,
                source_type=result.source_type,
                source_id=result.source_id,
            )
            link_announcement_event(event, result.source_id)
    logger.info("Wrote %s feed rollup events", written)
    return written


@app.task(queue="celery")
def run_militia_rollups(*, since_hours: int = 48) -> int:
    now = timezone.now()
    since = now - timedelta(hours=since_hours)
    ctx = build_context(since, now)
    results = run_all_rollups(ctx, codes=["militia_joins"])
    written = write_rollup_results(results)
    logger.info("Wrote %s militia rollup events", written)
    return written


@app.task(queue="celery")
def purge_feed_killmails() -> int:
    cutoff = timezone.now() - timedelta(days=FEED_KILLMAIL_RETENTION_DAYS)
    deleted, _ = FeedKillmail.objects.filter(killmail_time__lt=cutoff).delete()
    logger.info("Purged %s old FeedKillmail rows", deleted)
    return deleted
