"""A pilot's alliance history: what CEOs said when they left (design 06).

Matched by character ID and by account, so alts, including ones added to the
account after they left, are covered.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from django.contrib.auth.models import User
from django.db.models import Q

from eveonline.helpers.characters.identity import primary_characters_for_users
from eveonline.models import EveCharacter
from exits.helpers.grouping import group
from exits.models import STATUS_CONFIRMED, Departure, RejoinFlag


@dataclass
class HistoryEntry:
    departure_id: int
    corporation_id: int
    corporation_name: str
    left_at: datetime
    reason: str
    can_rejoin: bool | None
    note: str
    answered_by_name: str
    flag_active: bool


def character_ids_for(
    user: User | None, character_ids: Iterable[int]
) -> set[int]:
    ids = {int(character_id) for character_id in character_ids}
    if user is not None:
        ids |= set(
            EveCharacter.objects.filter(user=user).values_list(
                "character_id", flat=True
            )
        )
    return ids


def _match(user: User | None, character_ids: Iterable[int]) -> Q:
    q = Q(character_id__in=character_ids_for(user, character_ids))
    if user is not None:
        q |= Q(user=user)
    return q


def _names(user_ids: set[int]) -> dict[int, str]:
    names = {
        user_id: character.character_name
        for user_id, character in primary_characters_for_users(
            user_ids
        ).items()
    }
    for user_id, name in EveCharacter.objects.filter(
        user_id__in=user_ids - set(names)
    ).values_list("user_id", "character_name"):
        names.setdefault(user_id, name)
    return names


def history_for(
    user: User | None, character_ids: Iterable[int]
) -> list[HistoryEntry]:
    departures = list(
        Departure.objects.filter(_match(user, character_ids))
        .filter(status=STATUS_CONFIRMED)
        .exclude(reason="")
        .select_related("corporation")
        .prefetch_related("flags")
    )
    names = _names({d.answered_by_id for d in departures if d.answered_by_id})
    entries = []
    for members in group(departures):
        lead = members[0]
        entries.append(
            HistoryEntry(
                departure_id=lead.pk,
                corporation_id=lead.corporation.corporation_id,
                corporation_name=lead.corporation.name,
                left_at=lead.first_missing_at,
                reason=lead.reason,
                can_rejoin=lead.can_rejoin,
                note=lead.note,
                answered_by_name=names.get(lead.answered_by_id, ""),
                flag_active=any(
                    f.cleared_at is None
                    for d in members
                    for f in d.flags.all()
                ),
            )
        )
    return entries


def active_flags_for(
    user: User | None, character_ids: Iterable[int]
) -> list[RejoinFlag]:
    return list(
        RejoinFlag.objects.filter(_match(user, character_ids))
        .filter(cleared_at__isnull=True)
        .select_related("corporation", "set_by")
        .order_by("-set_at")
    )
