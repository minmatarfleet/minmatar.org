"""Push tribe events to Discord and read interest back (Celery side).

Request handlers save the TribeEvent and queue these through
``queue_event_sync`` so Discord calls never run inside a web request.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from discord.client import DiscordClient
from discord.outbox import queue_channel_message
from tribes.helpers.events import (
    DEFAULT_LENGTH,
    STATUS_CANCELED,
    announcement_content,
    discord_event_payload,
    discord_event_url,
    event_ends,
)
from tribes.models import TribeEvent

logger = logging.getLogger(__name__)


def _event(event_id: int) -> TribeEvent | None:
    return (
        TribeEvent.objects.filter(pk=event_id)
        .select_related(
            "tribe_group__tribe", "tribe_group__group__discord_group"
        )
        .first()
    )


def queue_event_sync(task, event_id: int) -> None:
    """Run an event task from a worker once the transaction commits."""
    # pylint: disable=import-outside-toplevel
    from discord.outbox import on_commit_enqueue

    on_commit_enqueue(task, (event_id,), f"tribe event {event_id}")


def create_discord_event(event_id: int) -> bool:
    """Create the guild event, then announce it in the group's channel."""
    event = _event(event_id)
    if event is None or event.status != TribeEvent.STATUS_SCHEDULED:
        return False
    if event.discord_event_id:
        return update_discord_event(event_id)
    created = DiscordClient().create_scheduled_event(
        discord_event_payload(event)
    )
    event.discord_event_id = int(created["id"])
    event.save(update_fields=["discord_event_id", "updated_at"])
    channel_id = event.tribe_group.effective_discord_channel_id
    if event.announce and channel_id:
        queue_channel_message(
            channel_id,
            message=announcement_content(
                event, discord_event_url(event.discord_event_id)
            ),
            context=f"tribe event {event.id} announcement",
        )
    return True


def update_discord_event(event_id: int) -> bool:
    event = _event(event_id)
    if event is None or event.status != TribeEvent.STATUS_SCHEDULED:
        return False
    if not event.discord_event_id:
        return create_discord_event(event_id)
    DiscordClient().edit_scheduled_event(
        event.discord_event_id, discord_event_payload(event)
    )
    return True


def cancel_discord_event(event_id: int) -> bool:
    event = _event(event_id)
    if event is None or not event.discord_event_id:
        return False
    DiscordClient().edit_scheduled_event(
        event.discord_event_id, {"status": STATUS_CANCELED}
    )
    return True


def _start(row: dict) -> datetime | None:
    value = row.get("scheduled_start_time")
    return parse_datetime(value) if value else None


def sync_event_interest(now: datetime | None = None) -> int:
    """Copy Discord's interested counts and close events that are over.

    A recurring event follows Discord's next occurrence. An event that has
    ended, or whose Discord event is gone after its start, is completed.
    Returns the number of events updated.
    """
    now = now or timezone.now()
    events = list(
        TribeEvent.objects.filter(status=TribeEvent.STATUS_SCHEDULED)
    )
    if not events:
        return 0
    rows = {}
    if any(event.discord_event_id for event in events):
        rows = {
            int(row["id"]): row
            for row in DiscordClient().list_scheduled_events(
                with_user_count=True
            )
        }
    updated = 0
    for event in events:
        row = rows.get(event.discord_event_id or 0)
        fields = []
        if row is not None:
            count = int(row.get("user_count") or 0)
            if count != event.interested_count:
                event.interested_count = count
                fields.append("interested_count")
            start = _start(row)
            if (
                event.recurrence != TribeEvent.RECURRENCE_NONE
                and start
                and start > event.starts_at
            ):
                length = (
                    event.ends_at - event.starts_at if event.ends_at else None
                )
                event.starts_at = start
                fields.append("starts_at")
                if length is not None:
                    event.ends_at = start + length
                    fields.append("ends_at")
        if _is_over(event, row, now):
            event.status = TribeEvent.STATUS_COMPLETED
            fields.append("status")
        if fields:
            event.save(update_fields=[*fields, "updated_at"])
            updated += 1
    return updated


def _is_over(event: TribeEvent, row: dict | None, now: datetime) -> bool:
    if event.recurrence == TribeEvent.RECURRENCE_NONE:
        return event_ends(event) < now
    # A recurring event lives as long as Discord keeps it.
    return (
        bool(event.discord_event_id)
        and row is None
        and (event.starts_at < now)
    )


def upcoming_events_q(now: datetime) -> Q:
    """Scheduled events not over yet, and ones cancelled in the last day."""
    still_on = Q(status=TribeEvent.STATUS_SCHEDULED) & (
        Q(ends_at__gte=now)
        | Q(ends_at__isnull=True, starts_at__gte=now - DEFAULT_LENGTH)
        | ~Q(recurrence=TribeEvent.RECURRENCE_NONE)
    )
    recently_cancelled = Q(
        status=TribeEvent.STATUS_CANCELLED,
        cancelled_at__gte=now - timedelta(hours=24),
    )
    return still_on | recently_cancelled
