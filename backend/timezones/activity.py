"""When pilots were on, from what the site already records.

One event per fleet joined, per killmail (as attacker or victim, from the
pilot's own ESI killmails and the zKillboard feed, counted once), and per
clock hour with voice in a tracked channel. Alts fold into their owner.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Iterable

from django.contrib.auth.models import User

from discord.models import DiscordChannelActivityRecord
from eveonline.helpers.characters.identity import character_ids_for_users
from eveonline.models import EveCharacterKillmail, EveCharacterKillmailAttacker
from feed.models import FeedKillmail
from fleets.models import EveFleetInstanceMember


def load_events(
    user_ids: Iterable[int], since: datetime
) -> dict[int, list[datetime]]:
    """User id -> aware datetimes of their activity since ``since``."""
    user_ids = {int(uid) for uid in user_ids if uid}
    if not user_ids:
        return {}
    char_to_user = character_ids_for_users(user_ids)
    events: dict[int, list[datetime]] = defaultdict(list)
    if char_to_user:
        _fleet_events(char_to_user, since, events)
        _killmail_events(char_to_user, since, events)
    _voice_events(user_ids, since, events)
    return dict(events)


def _fleet_events(char_to_user, since, events) -> None:
    first_join: dict[tuple[int, int], datetime] = {}
    for character_id, instance_id, join_time in (
        EveFleetInstanceMember.objects.filter(
            character_id__in=list(char_to_user), join_time__gte=since
        )
        .values_list("character_id", "eve_fleet_instance_id", "join_time")
        .iterator()
    ):
        key = (char_to_user[character_id], instance_id)
        if key not in first_join or join_time < first_join[key]:
            first_join[key] = join_time
    for (user_id, _), join_time in first_join.items():
        events[user_id].append(join_time)


def _killmail_events(char_to_user, since, events) -> None:
    seen: set[tuple[int, int]] = set()

    def add(character_id, killmail_id, killmail_time):
        user_id = char_to_user.get(character_id)
        if user_id is None or (user_id, killmail_id) in seen:
            return
        seen.add((user_id, killmail_id))
        events[user_id].append(killmail_time)

    character_ids = list(char_to_user)
    for row in (
        EveCharacterKillmailAttacker.objects.filter(
            character_id__in=character_ids,
            killmail__killmail_time__gte=since,
        )
        .values_list(
            "character_id",
            "killmail__killmail_id",
            "killmail__killmail_time",
        )
        .iterator()
    ):
        add(*row)
    for row in (
        EveCharacterKillmail.objects.filter(
            victim_character_id__in=character_ids, killmail_time__gte=since
        )
        .values_list("victim_character_id", "killmail_id", "killmail_time")
        .iterator()
    ):
        add(*row)
    # The feed has no per-character index, so scan the window once.
    for killmail_id, killmail_time, victim_id, attackers in (
        FeedKillmail.objects.filter(killmail_time__gte=since)
        .values_list(
            "killmail_id",
            "killmail_time",
            "victim_character_id",
            "attacker_summary",
        )
        .iterator(chunk_size=5000)
    ):
        add(victim_id, killmail_id, killmail_time)
        for attacker in attackers or ():
            if isinstance(attacker, dict):
                add(attacker.get("character_id"), killmail_id, killmail_time)


def _voice_events(user_ids, since, events) -> None:
    usernames = dict(
        User.objects.filter(id__in=user_ids).values_list("username", "id")
    )
    hours: set[tuple[int, datetime]] = set()
    for username, created_on in (
        DiscordChannelActivityRecord.objects.filter(
            activity_type=DiscordChannelActivityRecord.VOICE_MINUTE,
            created_on__gte=since,
            username__in=list(usernames),
        )
        .values_list("username", "created_on")
        .iterator()
    ):
        hour = created_on.replace(minute=0, second=0, microsecond=0)
        hours.add((usernames[username], hour))
    for user_id, hour in hours:
        events[user_id].append(hour)
