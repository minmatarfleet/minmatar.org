"""90-day fleet, kill, and voice activity for corporation members."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Count, Sum
from django.utils import timezone

from discord.models import DiscordChannelActivityRecord
from eveonline.helpers.corporations.kills import ACTIVITY_DAYS, RecentKills
from eveonline.models import EveCharacter
from fleets.models import EveFleetInstanceMember


def activity_for_characters(
    characters: list[EveCharacter],
    kills: RecentKills | None = None,
) -> dict[int, dict]:
    character_ids = [character.character_id for character in characters]
    user_ids = [
        character.user_id for character in characters if character.user_id
    ]
    cutoff = timezone.now() - timedelta(days=ACTIVITY_DAYS)
    fleets = {
        row["character_id"]: row["n"]
        for row in EveFleetInstanceMember.objects.filter(
            character_id__in=character_ids,
            join_time__gte=cutoff,
        )
        .values("character_id")
        .annotate(n=Count("eve_fleet_instance_id", distinct=True))
    }
    if kills is None:
        kills = RecentKills(character_ids)
    kill_counts = kills.kills_by_character(character_ids)
    voice_by_user = _voice_hours_by_user(user_ids, cutoff)
    payload = {}
    for character in characters:
        payload[character.character_id] = {
            "fleets_90d": int(fleets.get(character.character_id, 0)),
            "kills_90d": int(kill_counts.get(character.character_id, 0)),
            "voice_hours_90d": voice_by_user.get(character.user_id, 0.0),
        }
    return payload


def _voice_hours_by_user(user_ids: list[int], cutoff) -> dict[int, float]:
    if not user_ids:
        return {}
    usernames = {
        username: user_id
        for user_id, username in User.objects.filter(
            id__in=user_ids
        ).values_list("id", "username")
        if username
    }
    if not usernames:
        return {}
    totals = (
        DiscordChannelActivityRecord.objects.filter(
            username__in=list(usernames),
            activity_type=DiscordChannelActivityRecord.VOICE_MINUTE,
            created_on__gte=cutoff,
        )
        .values("username")
        .annotate(total=Sum("quantity"))
    )
    hours = {}
    for row in totals:
        user_id = usernames.get(row["username"])
        if user_id is None:
            continue
        minutes = int(row["total"] or 0)
        hours[user_id] = round(minutes / 60, 1)
    return hours
