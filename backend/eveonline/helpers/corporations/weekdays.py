"""When a corporation flies: fleets and kills per EVE-time weekday.

Pilot timezones live in the timezones app (timezones.services).
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from app.eve_time import as_eve_time
from eveonline.helpers.characters.identity import character_ids_for_users
from eveonline.helpers.corporations.kills import RecentKills
from eveonline.models import EveCharacter
from fleets.models import EveFleetInstanceMember

OBSERVED_DAYS = 90


def weekday_distribution(
    user_ids: list[int],
    corporation_id: int | None = None,
    days: int = OBSERVED_DAYS,
    kills: RecentKills | None = None,
) -> list[dict]:
    """People on fleets and kills per EVE-time weekday (0 = Monday).

    Alts fold into their owner, so a person counts once per weekday.
    A killmail counts once however many members were on it.
    """
    kill_days = _kills_by_weekday(corporation_id, days, kills)
    ids = sorted({int(uid) for uid in user_ids if uid})
    members = {day: set() for day in range(7)}
    if ids:
        char_to_user = character_ids_for_users(ids)
        cutoff = timezone.now() - timedelta(days=days)
        rows = EveFleetInstanceMember.objects.filter(
            character_id__in=list(char_to_user),
            join_time__gte=cutoff,
        ).values_list("character_id", "join_time")
        for character_id, join_time in rows:
            user_id = char_to_user.get(character_id)
            if not user_id or join_time is None:
                continue
            members[as_eve_time(join_time).weekday()].add(user_id)
    return [
        {"day": day, "members": len(members[day]), "kills": kill_days[day]}
        for day in range(7)
    ]


def _kills_by_weekday(
    corporation_id: int | None, days: int, kills: RecentKills | None
) -> list[int]:
    counts = [0] * 7
    if not corporation_id:
        return counts
    character_ids = list(
        EveCharacter.objects.filter(corporation_id=corporation_id).values_list(
            "character_id", flat=True
        )
    )
    if not character_ids:
        return counts
    if kills is None:
        kills = RecentKills(character_ids, days)
    for killmail_id in kills.killmails_for(character_ids):
        killmail_time = kills.times.get(killmail_id)
        if killmail_time is not None:
            counts[as_eve_time(killmail_time).weekday()] += 1
    return counts
