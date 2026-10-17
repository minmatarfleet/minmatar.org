"""Declared prime time and observed fleet-activity timezones."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone as dt_timezone

from django.utils import timezone

from eveonline.helpers.characters.identity import character_ids_for_users
from eveonline.helpers.corporations.kills import RecentKills
from eveonline.models import EveCharacter, EvePlayer
from fleets.endpoints.helpers import time_region
from fleets.models import EveFleetInstanceMember

PRIME_BUCKETS = ("US", "US_AP", "AP", "AP_EU", "EU", "EU_US")
OBSERVED_DAYS = 90
MIN_FLEETS = 2
MIN_SHARE = 0.10


def prime_time_codes_for_users(user_ids: list[int]) -> dict[int, str]:
    ids = sorted({int(uid) for uid in user_ids if uid})
    if not ids:
        return {}
    return {
        user_id: prime_time
        for user_id, prime_time in EvePlayer.objects.filter(user_id__in=ids)
        .exclude(prime_time__isnull=True)
        .exclude(prime_time="")
        .values_list("user_id", "prime_time")
        if user_id and prime_time in PRIME_BUCKETS
    }


def observed_prime_buckets_for_users(
    user_ids: list[int], days: int = OBSERVED_DAYS
) -> dict[int, list[str]]:
    """Fleet-attendance buckets a user is actually active in.

    A bucket is kept when it has at least two fleets or at least 10% of
    that user's fleets in the window, ordered by frequency.
    """
    ids = sorted({int(uid) for uid in user_ids if uid})
    if not ids:
        return {}
    char_to_user = character_ids_for_users(ids)
    if not char_to_user:
        return {}
    cutoff = timezone.now() - timedelta(days=days)
    counts: dict[int, dict[str, set[int]]] = defaultdict(
        lambda: defaultdict(set)
    )
    rows = EveFleetInstanceMember.objects.filter(
        character_id__in=list(char_to_user),
        join_time__gte=cutoff,
    ).values_list("character_id", "join_time", "eve_fleet_instance_id")
    for character_id, join_time, instance_id in rows:
        user_id = char_to_user.get(character_id)
        if not user_id or join_time is None or instance_id is None:
            continue
        bucket = _bucket_for(join_time)
        if bucket is None:
            continue
        counts[user_id][bucket].add(instance_id)
    result: dict[int, list[str]] = {}
    for user_id, buckets in counts.items():
        totals = {
            bucket: len(instances) for bucket, instances in buckets.items()
        }
        total = sum(totals.values())
        kept = [
            bucket
            for bucket, fleet_count in sorted(
                totals.items(), key=lambda item: (-item[1], item[0])
            )
            if fleet_count >= MIN_FLEETS
            or (total and fleet_count / total >= MIN_SHARE)
        ]
        if kept:
            result[user_id] = kept
    return result


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
            members[_eve_time(join_time).weekday()].add(user_id)
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
            counts[_eve_time(killmail_time).weekday()] += 1
    return counts


def timezone_distribution(
    user_ids: list[int],
    declared: dict[int, str],
    observed: dict[int, list[str]],
) -> list[dict]:
    declared_counts = {bucket: 0 for bucket in PRIME_BUCKETS}
    observed_counts = {bucket: 0 for bucket in PRIME_BUCKETS}
    for user_id in {int(uid) for uid in user_ids if uid}:
        prime_time = declared.get(user_id)
        if prime_time in declared_counts:
            declared_counts[prime_time] += 1
        for bucket in observed.get(user_id, []):
            if bucket in observed_counts:
                observed_counts[bucket] += 1
    return [
        {
            "bucket": bucket,
            "declared": declared_counts[bucket],
            "observed": observed_counts[bucket],
        }
        for bucket in PRIME_BUCKETS
        if declared_counts[bucket] or observed_counts[bucket]
    ]


def _eve_time(join_time: datetime) -> datetime:
    aware = (
        timezone.make_aware(join_time)
        if timezone.is_naive(join_time)
        else join_time
    )
    return aware.astimezone(dt_timezone.utc)


def _bucket_for(join_time: datetime) -> str | None:
    bucket = time_region(_eve_time(join_time))
    if bucket not in PRIME_BUCKETS:
        return None
    return bucket
