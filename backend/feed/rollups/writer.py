from __future__ import annotations

from django.utils import timezone

from feed.models import (
    FeedEvent,
    FeedEventAnnouncementLink,
    FeedEventKillmailLink,
    FeedKillmail,
)
from feed.rollups.types import RollupResult


def write_rollup_results(results: list[RollupResult]) -> int:
    written = 0
    for result in results:
        event = _upsert_event(result)
        _sync_killmail_links(event, result.killmail_ids)
        written += 1
    return written


def _upsert_event(result: RollupResult) -> FeedEvent:
    lookup: dict = {"rollup_code": result.rollup_code}
    if result.cluster_key:
        lookup["cluster_key"] = result.cluster_key
    elif result.source_type and result.source_id is not None:
        lookup["source_type"] = result.source_type
        lookup["source_id"] = result.source_id
    else:
        lookup["cluster_key"] = (
            f"{result.rollup_code}:{result.occurred_at.isoformat()}"
        )

    defaults = {
        "kind": result.kind,
        "occurred_at": result.occurred_at,
        "title": result.title,
        "subheader": result.subheader,
        "preview": result.preview,
        "body": result.body,
        "payload": result.payload,
        "accent": result.accent,
        "rollup_version": result.rollup_version,
        "is_active": result.is_active,
        "expires_at": result.expires_at,
        "computed_at": timezone.now(),
    }
    matches = list(
        FeedEvent.objects.filter(**lookup).order_by("-occurred_at", "-id")
    )
    if not matches:
        return FeedEvent.objects.create(**lookup, **defaults)
    event = matches[0]
    if len(matches) > 1:
        FeedEvent.objects.filter(
            pk__in=[row.pk for row in matches[1:]]
        ).delete()
    for field, value in defaults.items():
        setattr(event, field, value)
    event.save()
    return event


def _sync_killmail_links(event: FeedEvent, killmail_ids: list[int]) -> None:
    if not killmail_ids:
        return
    existing = set(
        FeedEventKillmailLink.objects.filter(feed_event=event).values_list(
            "feed_killmail_id", flat=True
        )
    )
    killmails = FeedKillmail.objects.filter(killmail_id__in=killmail_ids)
    for km in killmails:
        if km.id not in existing:
            FeedEventKillmailLink.objects.create(
                feed_event=event, feed_killmail=km
            )


def link_announcement_event(event: FeedEvent, announcement_id: int) -> None:
    FeedEventAnnouncementLink.objects.update_or_create(
        feed_event=event,
        defaults={"feed_announcement_id": announcement_id},
    )
