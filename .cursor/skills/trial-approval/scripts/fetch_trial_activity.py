#!/usr/bin/env python3
"""
Fetch Alliance-affiliated trial users with fleet / kill / voice metrics.

Does NOT decide who to approve — the agent applies SKILL.md reasoning.

Emits full-window totals plus a recent (30d) slice and last-activity ages so
front-loaded then-gone pilots are visible.

Usage (from repo root):
  cd backend && pipenv run python ../.cursor/skills/trial-approval/scripts/fetch_trial_activity.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_DIR = REPO_ROOT / "backend"

sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

import django

django.setup()

from django.db.models import Count, F, Max, Sum
from django.utils import timezone

from discord.models import DiscordChannelActivityRecord
from eveonline.models import EveCharacter, EveCharacterKillmailAttacker, EvePlayer
from fleets.models import EveFleetInstanceMember
from groups.models import UserAffiliation, UserCommunityStatus

PRODUCTION_DB = "production_readonly"
RECENT_DAYS = 30


def gang_bucket(size: int) -> str:
    if size <= 10:
        return "small"
    if size <= 24:
        return "medium"
    if size <= 39:
        return "large"
    return "blob"


def days_since(now: datetime, when: Optional[datetime]) -> Optional[int]:
    if when is None:
        return None
    return (now - when).days


def empty_gangs() -> dict[str, int]:
    return {"small": 0, "medium": 0, "large": 0, "blob": 0}


def fetch_activity(
    *,
    days: int,
    affiliation_name: str,
) -> dict:
    now = timezone.now()
    since = now - timedelta(days=days)
    recent_since = now - timedelta(days=RECENT_DAYS)

    affiliations = list(
        UserAffiliation.objects.using(PRODUCTION_DB)
        .filter(affiliation__name=affiliation_name)
        .select_related("user", "affiliation")
    )
    user_ids = [a.user_id for a in affiliations]
    affiliation_meta = {
        a.user_id: {
            "affiliation": a.affiliation.name,
            "requires_trial": bool(a.affiliation.requires_trial),
        }
        for a in affiliations
    }
    status_by_user = {
        ucs.user_id: ucs.status
        for ucs in UserCommunityStatus.objects.using(PRODUCTION_DB).filter(
            user_id__in=user_ids
        )
    }

    trial_user_ids = [
        uid
        for uid in user_ids
        if status_by_user.get(uid) == UserCommunityStatus.STATUS_TRIAL
    ]
    trial_set = set(trial_user_ids)
    username_by_id = {
        a.user_id: a.user.username
        for a in affiliations
        if a.user_id in trial_set
    }

    primary_by_user = {
        ep.user_id: ep.primary_character.character_name
        for ep in (
            EvePlayer.objects.using(PRODUCTION_DB)
            .filter(user_id__in=trial_user_ids, primary_character__isnull=False)
            .select_related("primary_character")
        )
    }

    user_by_eve: dict[int, int] = {}
    eve_ids_by_user: dict[int, list[int]] = defaultdict(list)
    for user_id, character_id in (
        EveCharacter.objects.using(PRODUCTION_DB)
        .filter(user_id__in=trial_user_ids, character_id__isnull=False)
        .values_list("user_id", "character_id")
    ):
        user_by_eve[character_id] = user_id
        eve_ids_by_user[user_id].append(character_id)
    all_eve_ids = list(user_by_eve)

    fleets_by_user: dict[int, set[int]] = defaultdict(set)
    fleets_30d_by_user: dict[int, set[int]] = defaultdict(set)
    last_fleet_by_user: dict[int, datetime] = {}
    if all_eve_ids:
        for character_id, instance_id, join_time in (
            EveFleetInstanceMember.objects.using(PRODUCTION_DB)
            .filter(character_id__in=all_eve_ids, join_time__gte=since)
            .values_list("character_id", "eve_fleet_instance_id", "join_time")
            .iterator(chunk_size=5000)
        ):
            uid = user_by_eve.get(character_id)
            if uid is None:
                continue
            fleets_by_user[uid].add(instance_id)
            if join_time >= recent_since:
                fleets_30d_by_user[uid].add(instance_id)
            prev = last_fleet_by_user.get(uid)
            if prev is None or join_time > prev:
                last_fleet_by_user[uid] = join_time

    gang_by_user: dict[int, dict[str, int]] = defaultdict(empty_gangs)
    gang_30d_by_user: dict[int, dict[str, int]] = defaultdict(empty_gangs)
    kills_by_user: dict[int, int] = defaultdict(int)
    kills_30d_by_user: dict[int, int] = defaultdict(int)
    last_kill_by_user: dict[int, datetime] = {}
    if all_eve_ids:
        kill_rows = (
            EveCharacterKillmailAttacker.objects.using(PRODUCTION_DB)
            .filter(
                character_id__in=all_eve_ids,
                killmail__killmail_time__gte=since,
            )
            .exclude(character_id=F("killmail__victim_character_id"))
            .annotate(
                gang_size=Count(
                    "killmail__evecharacterkillmailattacker", distinct=True
                )
            )
            .values_list("character_id", "gang_size", "killmail__killmail_time")
            .iterator(chunk_size=5000)
        )
        for character_id, gang_size, kill_time in kill_rows:
            uid = user_by_eve.get(character_id)
            if uid is None:
                continue
            kills_by_user[uid] += 1
            bucket = gang_bucket(gang_size)
            gang_by_user[uid][bucket] += 1
            if kill_time >= recent_since:
                kills_30d_by_user[uid] += 1
                gang_30d_by_user[uid][bucket] += 1
            prev = last_kill_by_user.get(uid)
            if prev is None or kill_time > prev:
                last_kill_by_user[uid] = kill_time

    usernames = list(username_by_id.values())
    voice_by_username: dict[str, int] = {}
    voice_30d_by_username: dict[str, int] = {}
    last_voice_by_username: dict[str, datetime] = {}
    if usernames:
        voice_by_username = {
            row["username"]: int(row["total"] or 0)
            for row in (
                DiscordChannelActivityRecord.objects.using(PRODUCTION_DB)
                .filter(
                    username__in=usernames,
                    activity_type="voice_minute",
                    created_on__gte=since,
                )
                .values("username")
                .annotate(total=Sum("quantity"))
            )
        }
        voice_30d_by_username = {
            row["username"]: int(row["total"] or 0)
            for row in (
                DiscordChannelActivityRecord.objects.using(PRODUCTION_DB)
                .filter(
                    username__in=usernames,
                    activity_type="voice_minute",
                    created_on__gte=recent_since,
                )
                .values("username")
                .annotate(total=Sum("quantity"))
            )
        }
        last_voice_by_username = {
            row["username"]: row["latest"]
            for row in (
                DiscordChannelActivityRecord.objects.using(PRODUCTION_DB)
                .filter(
                    username__in=usernames,
                    activity_type="voice_minute",
                    created_on__gte=since,
                )
                .values("username")
                .annotate(latest=Max("created_on"))
            )
            if row["latest"] is not None
        }

    members = []
    for user_id in trial_user_ids:
        username = username_by_id.get(user_id)
        if not username:
            continue
        char_ids = eve_ids_by_user.get(user_id, [])
        fleets = len(fleets_by_user.get(user_id, ()))
        fleets_30d = len(fleets_30d_by_user.get(user_id, ()))
        voice_min = voice_by_username.get(username, 0)
        voice_min_30d = voice_30d_by_username.get(username, 0)
        gangs = gang_by_user.get(user_id, empty_gangs())
        gangs_30d = gang_30d_by_user.get(user_id, empty_gangs())
        meta = affiliation_meta.get(
            user_id, {"affiliation": affiliation_name, "requires_trial": True}
        )

        last_fleet = last_fleet_by_user.get(user_id)
        last_kill = last_kill_by_user.get(user_id)
        last_voice = last_voice_by_username.get(username)
        activity_times = [t for t in (last_fleet, last_kill, last_voice) if t]
        last_activity = max(activity_times) if activity_times else None

        members.append(
            {
                "username": username,
                "primary_character": primary_by_user.get(user_id),
                "previous_status": UserCommunityStatus.STATUS_TRIAL,
                "affiliation": meta["affiliation"],
                "requires_trial": meta["requires_trial"],
                "linked_character_count": len(char_ids),
                "fleets": fleets,
                "kills": kills_by_user.get(user_id, 0),
                "kills_small": gangs["small"],
                "kills_medium": gangs["medium"],
                "kills_large": gangs["large"],
                "kills_blob": gangs["blob"],
                "voice_minutes": voice_min,
                "voice_hours": round(voice_min / 60, 1),
                "fleets_30d": fleets_30d,
                "kills_30d": kills_30d_by_user.get(user_id, 0),
                "kills_small_30d": gangs_30d["small"],
                "voice_minutes_30d": voice_min_30d,
                "voice_hours_30d": round(voice_min_30d / 60, 1),
                "days_since_fleet": days_since(now, last_fleet),
                "days_since_kill": days_since(now, last_kill),
                "days_since_voice": days_since(now, last_voice),
                "days_since_activity": days_since(now, last_activity),
            }
        )

    members.sort(
        key=lambda m: (
            -(m["fleets"] + m["kills_small"] + int(m["voice_hours"])),
            m["username"],
        )
    )

    return {
        "as_of": now.strftime("%Y-%m-%d"),
        "window_days": days,
        "recent_days": RECENT_DAYS,
        "affiliation": affiliation_name,
        "community_status": "trial",
        "member_count": len(members),
        "members": members,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch trial Alliance member fleet/kill/voice activity"
    )
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout")
    parser.add_argument("--days", type=int, default=90, help="Lookback window")
    parser.add_argument(
        "--affiliation",
        default="Alliance",
        help="AffiliationType.name to include",
    )
    args = parser.parse_args()
    payload = fetch_activity(
        days=args.days,
        affiliation_name=args.affiliation,
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
