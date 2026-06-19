from __future__ import annotations

from django.utils import timezone

from feed.models import FeedAnnouncement, FeedEvent
from feed.rollups.config import get_rollup_version
from feed.rollups.types import RollupContext, RollupResult


def run_announcement_rollup(ctx: RollupContext) -> list[RollupResult]:
    version = get_rollup_version("communication")
    now = timezone.now()
    announcements = FeedAnnouncement.objects.filter(
        is_published=True,
        published_at__isnull=False,
        published_at__gte=ctx.since,
        published_at__lte=ctx.until,
    )
    results: list[RollupResult] = []
    for ann in announcements:
        if ann.expires_at and ann.expires_at < now:
            continue
        preview = ann.message[:72] + ("…" if len(ann.message) > 72 else "")
        results.append(
            RollupResult(
                kind=FeedEvent.Kind.COMMUNICATION,
                occurred_at=ann.published_at,
                title=ann.title,
                subheader=ann.author_display or "Fleet command",
                preview=preview,
                body=ann.message,
                accent=FeedEvent.Accent.COMBAT,
                payload={
                    "author": ann.author_display,
                    "announcement_id": ann.id,
                },
                rollup_code="communication",
                rollup_version=version,
                source_type="announcement",
                source_id=ann.id,
                expires_at=ann.expires_at,
            )
        )
    return results
