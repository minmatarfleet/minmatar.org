"""Retention for AllianceHealthSnapshot rows.

A snapshot is saved every hour, each holding the whole health payload, so the
table grows by about 8,800 large rows a year. Readers only need:

- the latest snapshot (dashboard, corp pages, give-back card, status
  patches), and
- the latest snapshot at or before 30 days ago (the overview's month-on-month
  comparison).

Every snapshot from the last ``KEEP_ALL_DAYS`` days is kept, which covers
the 30-day comparison with margin at hourly resolution, so those reads
return exactly what they did before. Older than that, the last snapshot of
each UTC day is kept as a daily history and the rest are deleted.
"""

from __future__ import annotations

import logging
from datetime import timedelta, timezone as dt_timezone

from django.utils import timezone

from alliance.models import AllianceHealthSnapshot

logger = logging.getLogger(__name__)

KEEP_ALL_DAYS = 35
DELETE_BATCH = 500


def prunable_snapshot_ids(now=None) -> list[int]:
    """Snapshots older than the window that are not their day's last."""
    now = now or timezone.now()
    cutoff = now - timedelta(days=KEEP_ALL_DAYS)
    rows = (
        AllianceHealthSnapshot.objects.filter(computed_at__lt=cutoff)
        .order_by("computed_at", "id")
        .values_list("id", "computed_at")
    )
    last_of_day: dict = {}
    ids = []
    for pk, computed_at in rows.iterator():
        ids.append(pk)
        # Ordered ascending, so the last write per day wins.
        last_of_day[computed_at.astimezone(dt_timezone.utc).date()] = pk
    keep = set(last_of_day.values())
    return [pk for pk in ids if pk not in keep]


def prune_alliance_health_snapshots(*, dry_run: bool = False) -> int:
    """Delete snapshots outside the retention set; returns how many."""
    ids = prunable_snapshot_ids()
    logger.info(
        "Alliance health snapshots: %s to prune%s",
        len(ids),
        " (dry run)" if dry_run else "",
    )
    if dry_run:
        return len(ids)
    deleted = 0
    for start in range(0, len(ids), DELETE_BATCH):
        batch = ids[start : start + DELETE_BATCH]
        deleted += AllianceHealthSnapshot.objects.filter(
            id__in=batch
        ).delete()[0]
    return deleted
