"""Background work for the affiliation database (the ``intel`` queue)."""

from __future__ import annotations

import logging

from datetime import timedelta

from django.db.models import F
from django.utils import timezone

from app.celery import app
from intel.affiliations import resolve, score, sightings
from intel.affiliations.constants import INVESTIGATIONS_PER_RUN
from intel.affiliations.investigate import investigate
from intel.models import IntelEntity

logger = logging.getLogger(__name__)


@app.task(exclusive=30 * 60)
def collect_intel_sightings() -> dict:
    stats = sightings.collect()
    logger.info("Intel sightings: %s", stats)
    return stats


STUCK_AFTER = timedelta(hours=1)


def requeue_stuck() -> int:
    """Investigations a dead worker left half done go back in the queue."""
    return IntelEntity.objects.filter(
        status=IntelEntity.Status.INVESTIGATING,
        updated_at__lt=timezone.now() - STUCK_AFTER,
    ).update(status=IntelEntity.Status.QUEUED, updated_at=timezone.now())


def next_queued(limit: int = INVESTIGATIONS_PER_RUN) -> list[IntelEntity]:
    return list(
        IntelEntity.objects.filter(status=IntelEntity.Status.QUEUED).order_by(
            "-priority", F("queued_at").asc(nulls_first=True), "-sightings"
        )[:limit]
    )


# About 50 zKill requests a group at ~1 a second: a run takes a few minutes,
# and never overlaps the next.
@app.task(expires=10 * 60, exclusive=20 * 60)
def investigate_queued_groups() -> dict:
    stats = {
        "requeued": requeue_stuck(),
        "investigated": 0,
        "failed": 0,
        "suggested": 0,
    }
    for entity in next_queued():
        result = investigate(entity)
        if result.get("failed"):
            stats["failed"] += 1
            # zKill is down: the rest wait for the next run.
            break
        stats["investigated"] += 1
        score.queue_partners(entity)
        stats["suggested"] += bool(score.score_group(entity))
        resolve.invalidate()
    logger.info("Intel investigations: %s", stats)
    return stats


@app.task(exclusive=60 * 60)
def score_intel_affiliations() -> dict:
    stats = score.score_all()
    logger.info("Intel affiliation scoring: %s", stats)
    return stats
