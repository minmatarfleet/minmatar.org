"""Count where we see groups, and queue the ones worth investigating.

An hourly pass reads what arrived since the last one: killmails in the feed
(attackers and victims) and shared Local reports. A group seen often
enough is queued; one in a Local report is queued at once. A group we
investigated a month ago and still see is queued again for its new months.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta

from django.core.cache import cache
from django.db.models import F
from django.utils import timezone

from feed.models import FeedKillmail
from intel.affiliations.constants import (
    LOCAL_REPORT_SIGHTINGS,
    QUEUE_AFTER_SIGHTINGS,
    REINVESTIGATE_DAYS,
    RETRY_FAILED_HOURS,
)
from intel.affiliations.investigate import group_of
from intel.models import IntelEntity, IntelReport

logger = logging.getLogger(__name__)

CURSOR_KEY = "intel:sightings:cursor"
FIRST_WINDOW = timedelta(hours=1)

Status = IntelEntity.Status


def note_sightings(counts: Counter, *, now: datetime | None = None) -> int:
    """Add ``{(kind, eve_id): times}`` and queue whoever is now due."""
    if not counts:
        return 0
    now = now or timezone.now()
    keys = list(counts)
    existing = set(
        IntelEntity.objects.filter(
            eve_id__in={eve_id for _, eve_id in keys}
        ).values_list("kind", "eve_id")
    )
    IntelEntity.objects.bulk_create(
        [
            IntelEntity(kind=kind, eve_id=eve_id, first_seen_at=now)
            for kind, eve_id in keys
            if (kind, eve_id) not in existing
        ],
        ignore_conflicts=True,
    )
    by_times: dict[int, list] = {}
    for key, times in counts.items():
        by_times.setdefault(times, []).append(key)
    seen_ids = []
    for times, group in by_times.items():
        for kind in {kind for kind, _ in group}:
            rows = IntelEntity.objects.filter(
                kind=kind,
                eve_id__in=[eve_id for k, eve_id in group if k == kind],
            )
            seen_ids.extend(rows.values_list("pk", flat=True))
            rows.update(
                sightings=F("sightings") + times,
                last_seen_at=now,
                updated_at=now,
            )
    seen = IntelEntity.objects.filter(pk__in=seen_ids)
    seen.filter(first_seen_at__isnull=True).update(first_seen_at=now)
    queued = seen.filter(
        status=Status.NEW, sightings__gte=QUEUE_AFTER_SIGHTINGS
    ).update(status=Status.QUEUED, queued_at=now)
    queued += seen.filter(
        status=Status.DONE,
        investigated_at__lt=now - timedelta(days=REINVESTIGATE_DAYS),
    ).update(status=Status.QUEUED, queued_at=now)
    queued += seen.filter(
        status=Status.FAILED,
        updated_at__lt=now - timedelta(hours=RETRY_FAILED_HOURS),
    ).update(status=Status.QUEUED, queued_at=now)
    return queued


def killmail_sightings(since: datetime, until: datetime) -> Counter:
    """Each group once per feed killmail it was on (either side)."""
    counts: Counter = Counter()
    rows = FeedKillmail.objects.filter(
        created_at__gte=since, created_at__lt=until
    ).values_list("attacker_summary", "raw_killmail__victim")
    for attackers, victim in rows:
        groups = {group_of(attacker) for attacker in attackers or []}
        groups.add(group_of(victim or {}))
        counts.update(groups - {None})
    return counts


def local_sightings(since: datetime, until: datetime) -> Counter:
    """Every group in a Local report shared in the window."""
    counts: Counter = Counter()
    summaries = IntelReport.objects.filter(
        kind=IntelReport.Kind.LOCAL,
        created_at__gte=since,
        created_at__lt=until,
    ).values_list("summary", flat=True)
    for summary in summaries:
        for row in (summary or {}).get("alliances") or []:
            if row.get("id"):
                counts[
                    (IntelEntity.Kind.ALLIANCE, int(row["id"]))
                ] += LOCAL_REPORT_SIGHTINGS
        for row in (summary or {}).get("corporations") or []:
            if row.get("id"):
                counts[
                    (IntelEntity.Kind.CORPORATION, int(row["id"]))
                ] += LOCAL_REPORT_SIGHTINGS
    return counts


def collect(now: datetime | None = None) -> dict:
    """Count everything since the last pass and queue who is due."""
    now = now or timezone.now()
    try:
        since = cache.get(CURSOR_KEY)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Sightings cursor unavailable", exc_info=True)
        since = None
    since = since or now - FIRST_WINDOW
    counts = killmail_sightings(since, now) + local_sightings(since, now)
    queued = note_sightings(counts, now=now)
    try:
        cache.set(CURSOR_KEY, now, None)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Sightings cursor not saved", exc_info=True)
    return {"groups": len(counts), "queued": queued}
