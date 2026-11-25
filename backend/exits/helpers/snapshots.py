"""Compare a tracked corporation's member list with the one stored last time.

A failed or empty ESI read is never "everyone left": an empty list is skipped
and the stored list is kept (design 03).
"""

from dataclasses import dataclass, field
from datetime import datetime

from django.db import transaction

from eveonline.models import EveCharacter, EveCorporation
from exits.models import (
    STATUS_DROPPED,
    STATUS_PENDING,
    Departure,
    MemberSnapshot,
)

SKIP_FIRST_SYNC = "first_sync"
SKIP_EMPTY = "empty"
SKIP_ALLIANCE_CHANGED = "alliance_changed"


@dataclass
class SnapshotResult:
    left: set[int] = field(default_factory=set)
    joined: set[int] = field(default_factory=set)
    skipped: str = ""


def _alliance_id(corporation: EveCorporation) -> int | None:
    return corporation.alliance.alliance_id if corporation.alliance else None


def _drop_pending(corporation: EveCorporation, character_ids=None) -> None:
    pending = Departure.objects.filter(
        corporation=corporation, status=STATUS_PENDING
    )
    if character_ids is not None:
        pending = pending.filter(character_id__in=character_ids)
    pending.update(status=STATUS_DROPPED)


def _store(corporation, member_ids, alliance_id, now) -> None:
    MemberSnapshot.objects.update_or_create(
        corporation=corporation,
        defaults={
            "member_ids": member_ids,
            "alliance_id": alliance_id,
            "taken_at": now,
        },
    )


def _open_departures(corporation, character_ids, now) -> None:
    already = set(
        Departure.objects.filter(
            corporation=corporation,
            status=STATUS_PENDING,
            character_id__in=character_ids,
        ).values_list("character_id", flat=True)
    )
    users = dict(
        EveCharacter.objects.filter(
            character_id__in=character_ids, user__isnull=False
        ).values_list("character_id", "user_id")
    )
    Departure.objects.bulk_create(
        Departure(
            corporation=corporation,
            character_id=character_id,
            user_id=users.get(character_id),
            first_missing_at=now,
        )
        for character_id in sorted(character_ids - already)
    )


@transaction.atomic
def record_members(
    corporation: EveCorporation, member_ids: list[int], now: datetime
) -> SnapshotResult:
    """Store the member list and return who left and who joined since last time."""
    if not member_ids:
        return SnapshotResult(skipped=SKIP_EMPTY)

    members = {int(character_id) for character_id in member_ids}
    stored_ids = sorted(members)
    alliance_id = _alliance_id(corporation)
    snapshot = (
        MemberSnapshot.objects.select_for_update()
        .filter(corporation=corporation)
        .first()
    )

    if snapshot is None:
        _store(corporation, stored_ids, alliance_id, now)
        return SnapshotResult(skipped=SKIP_FIRST_SYNC)

    if snapshot.alliance_id != alliance_id:
        _drop_pending(corporation)
        _store(corporation, stored_ids, alliance_id, now)
        return SnapshotResult(skipped=SKIP_ALLIANCE_CHANGED)

    previous = set(snapshot.member_ids)
    left = previous - members
    joined = members - previous

    _drop_pending(corporation, members)
    _open_departures(corporation, left, now)
    _store(corporation, stored_ids, alliance_id, now)
    return SnapshotResult(left=left, joined=joined)


@transaction.atomic
def stop_tracking(corporation: EveCorporation) -> None:
    """Forget the stored list and drop pending departures (Track exits unticked)."""
    MemberSnapshot.objects.filter(corporation=corporation).delete()
    _drop_pending(corporation)
