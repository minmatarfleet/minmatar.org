"""Confirm pending departures once the grace period has passed (design 03).

The destination comes from ``EveCharacter.corporation_id``, which the
15-minute affiliation sync keeps fresh, so no ESI calls are made here.
"""

from datetime import datetime, timedelta

from django.db import transaction

from eveonline.helpers.alliances import alliance_corporations
from eveonline.models import EveCharacter, EveCorporation
from exits.models import (
    KIND_ALLIANCE_MOVE,
    KIND_EXIT,
    STATUS_CONFIRMED,
    STATUS_DROPPED,
    STATUS_PENDING,
    Departure,
)

GRACE = timedelta(hours=48)

NPC_CORPORATION_MIN = 1000000
NPC_CORPORATION_MAX = 1999999


def is_npc_corporation(corporation_id: int | None) -> bool:
    return (
        corporation_id is not None
        and NPC_CORPORATION_MIN <= corporation_id <= NPC_CORPORATION_MAX
    )


def _alliance_move_ids() -> set[int]:
    """Corporations a pilot can move to and still be in the alliance."""
    ids = set(alliance_corporations().values_list("corporation_id", flat=True))
    ids |= set(
        EveCorporation.objects.filter(track_exits=True).values_list(
            "corporation_id", flat=True
        )
    )
    return ids


def classify(
    destination_corporation_id: int | None, alliance_move_ids=None
) -> str:
    if alliance_move_ids is None:
        alliance_move_ids = _alliance_move_ids()
    if destination_corporation_id in alliance_move_ids:
        return KIND_ALLIANCE_MOVE
    return KIND_EXIT


@transaction.atomic
def confirm_due(now: datetime) -> int:
    """Confirm or drop every pending departure older than ``GRACE``."""
    due = list(
        Departure.objects.select_for_update()
        .filter(status=STATUS_PENDING, first_missing_at__lte=now - GRACE)
        .select_related("corporation")
    )
    if not due:
        return 0
    corporations = dict(
        EveCharacter.objects.filter(
            character_id__in=[d.character_id for d in due]
        ).values_list("character_id", "corporation_id")
    )
    alliance_move_ids = _alliance_move_ids()
    confirmed = 0
    for departure in due:
        destination = corporations.get(departure.character_id)
        if destination == departure.corporation.corporation_id:
            departure.status = STATUS_DROPPED
            departure.save(update_fields=["status"])
            continue
        departure.status = STATUS_CONFIRMED
        departure.confirmed_at = now
        departure.destination_corporation_id = destination
        departure.kind = classify(destination, alliance_move_ids)
        departure.destination_is_npc = is_npc_corporation(destination)
        departure.save(
            update_fields=[
                "status",
                "confirmed_at",
                "destination_corporation_id",
                "kind",
                "destination_is_npc",
            ]
        )
        confirmed += 1
    return confirmed
