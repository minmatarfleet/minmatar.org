"""Read every character's notifications from ESI and keep all of them.

This is the only scheduled caller of ``/characters/{id}/notifications/``
(the tech router keeps a live debug view). Features that need notifications
(structure pings, FW payouts) read ``EveCharacterNotification`` instead of
polling ESI themselves, so a character is fetched once per cycle however
many features care about it.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone as dt_timezone

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from eveonline import esi_budget
from eveonline.client import EsiClient
from eveonline.models import EveCharacter, EveCharacterNotification

logger = logging.getLogger(__name__)

NOTIFICATION_SCOPE = "esi-characters.read_notifications.v1"

# ESI's per-character notification bucket allows about seven full fetches per
# 15 minutes, and the endpoint is cached for 10, so a faster poll only buys
# 304s.
POLL_BUCKETS = 10


def characters_with_notification_scope():
    """Every character whose token can read notifications."""
    return EveCharacter.objects.filter(
        token__scopes__name=NOTIFICATION_SCOPE,
        esi_deleted=False,
        esi_suspended=False,
    ).distinct()


def character_ids_for_minute(minute: int) -> list[int]:
    """This minute's share of the roster, so each character is read every
    ``POLL_BUCKETS`` minutes."""
    bucket = minute % POLL_BUCKETS
    return [
        character_id
        for character_id in characters_with_notification_scope()
        .order_by("character_id")
        .values_list("character_id", flat=True)
        if character_id % POLL_BUCKETS == bucket
    ]


def _as_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_datetime(value) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = parse_datetime(value.strip())
    else:
        return None
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, dt_timezone.utc)
    return parsed


def _row(
    character: EveCharacter, notification
) -> EveCharacterNotification | None:
    if not isinstance(notification, dict):
        return None
    notification_id = _as_int(notification.get("notification_id"))
    timestamp = _as_datetime(notification.get("timestamp"))
    notification_type = notification.get("type")
    if notification_id is None or timestamp is None or not notification_type:
        return None
    is_read = notification.get("is_read")
    return EveCharacterNotification(
        character=character,
        notification_id=notification_id,
        type=str(notification_type)[:128],
        sender_id=_as_int(notification.get("sender_id")),
        sender_type=str(notification.get("sender_type") or "")[:32],
        timestamp=timestamp,
        is_read=is_read if isinstance(is_read, bool) else None,
        text=str(notification.get("text") or ""),
    )


def store_notifications(character: EveCharacter, notifications) -> int:
    """Store the notifications we have not seen. Returns how many were new.

    A notification never changes after it is sent, so a row we already have
    is left alone (``is_read`` included: it is the in-game state at the time
    we first read it).
    """
    rows = {}
    for notification in notifications or []:
        row = _row(character, notification)
        if row is not None:
            rows[row.notification_id] = row
    if not rows:
        return 0

    known = set(
        EveCharacterNotification.objects.filter(
            character=character, notification_id__in=list(rows)
        ).values_list("notification_id", flat=True)
    )
    new = [row for key, row in rows.items() if key not in known]
    # ignore_conflicts covers a second copy of this fetch racing this one.
    EveCharacterNotification.objects.bulk_create(new, ignore_conflicts=True)
    return len(new)


def fetch_notifications(character: EveCharacter) -> dict:
    """Fetch one character's notifications and store the new ones."""
    character_id = character.character_id
    if not esi_budget.can_spend("char-notification", character_id):
        return {"polled": 0, "stored": 0, "skipped": 1}

    try:
        response = EsiClient(character).get_character_notifications()
    except Exception:  # pylint: disable=broad-except
        logger.exception(
            "Notification fetch raised for %s", character.character_name
        )
        esi_budget.record_error()
        return {"polled": 0, "stored": 0, "skipped": 1}

    esi_budget.note_response("char-notification", character_id, response)

    if response.response_code == 304:
        return {"polled": 1, "stored": 0, "skipped": 0}
    if not response.success():
        # A 429 has paused this character in the budget; the next scheduled
        # poll tries again.
        logger.info(
            "Notification fetch failed for %s: %s",
            character.character_name,
            response.error_text(),
        )
        return {"polled": 1, "stored": 0, "skipped": 0}

    stored = store_notifications(character, response.results())
    return {"polled": 1, "stored": stored, "skipped": 0}
