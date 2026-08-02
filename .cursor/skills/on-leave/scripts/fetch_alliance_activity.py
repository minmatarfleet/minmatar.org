#!/usr/bin/env python3
"""
Fetch Alliance-affiliated active users with fleet / kill / voice metrics.

Usage (from repo root):
  cd backend && pipenv run python ../.cursor/skills/on-leave/scripts/fetch_alliance_activity.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_DIR = REPO_ROOT / "backend"

sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

import django

django.setup()

from django.db.models import Count, F, Sum
from django.utils import timezone

from discord.models import DiscordChannelActivityRecord
from eveonline.models import EveCharacter, EveCharacterKillmailAttacker, EvePlayer
from fleets.models import EveFleetInstanceMember
from groups.models import (
    UserAffiliation,
    UserCommunityStatus,
    UserCommunityStatusHistory,
)

PRODUCTION_DB = "production_readonly"
RESTORE_GRACE_DAYS = 30


def fetch_activity(
    *,
    days: int,
    affiliation_name: str,
    max_fleets: int | None,
) -> dict:
    now = timezone.now()
    since = now - timedelta(days=days)
    restore_since = now - timedelta(days=RESTORE_GRACE_DAYS)

    affiliations = list(
        UserAffiliation.objects.using(PRODUCTION_DB)
        .filter(affiliation__name=affiliation_name)
        .select_related("user", "affiliation")
    )
    user_ids = [a.user_id for a in affiliations]
    status_by_user = {
        ucs.user_id: ucs.status
        for ucs in UserCommunityStatus.objects.using(PRODUCTION_DB).filter(
            user_id__in=user_ids
        )
    }

    # Missing UCS is treated as active in app code.
    active_user_ids = [
        uid
        for uid in user_ids
        if status_by_user.get(uid, UserCommunityStatus.STATUS_ACTIVE)
        == UserCommunityStatus.STATUS_ACTIVE
    ]
    active_set = set(active_user_ids)
    username_by_id = {
        a.user_id: a.user.username
        for a in affiliations
        if a.user_id in active_set
    }

    primary_by_user = {
        ep.user_id: ep.primary_character.character_name
        for ep in (
            EvePlayer.objects.using(PRODUCTION_DB)
            .filter(user_id__in=active_user_ids, primary_character__isnull=False)
            .select_related("primary_character")
        )
    }

    user_by_eve: dict[int, int] = {}
    eve_ids_by_user: dict[int, list[int]] = defaultdict(list)
    for user_id, character_id in (
        EveCharacter.objects.using(PRODUCTION_DB)
        .filter(user_id__in=active_user_ids, character_id__isnull=False)
        .values_list("user_id", "character_id")
    ):
        user_by_eve[character_id] = user_id
        eve_ids_by_user[user_id].append(character_id)
    all_eve_ids = list(user_by_eve)

    fleets_by_user: dict[int, set[int]] = defaultdict(set)
    if all_eve_ids:
        for character_id, instance_id in (
            EveFleetInstanceMember.objects.using(PRODUCTION_DB)
            .filter(character_id__in=all_eve_ids, join_time__gte=since)
            .values_list("character_id", "eve_fleet_instance_id")
            .iterator(chunk_size=5000)
        ):
            uid = user_by_eve.get(character_id)
            if uid is not None:
                fleets_by_user[uid].add(instance_id)

    kills_by_char = {}
    if all_eve_ids:
        kills_by_char = {
            row["character_id"]: row["n"]
            for row in (
                EveCharacterKillmailAttacker.objects.using(PRODUCTION_DB)
                .filter(
                    character_id__in=all_eve_ids,
                    killmail__killmail_time__gte=since,
                )
                .exclude(character_id=F("killmail__victim_character_id"))
                .values("character_id")
                .annotate(n=Count("id"))
            )
        }

    usernames = list(username_by_id.values())
    voice_by_username = {}
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

    # Latest on_leave → non-leave within restore grace window.
    restored_at_by_user: dict[int, object] = {}
    if active_user_ids:
        for user_id, changed_at in (
            UserCommunityStatusHistory.objects.using(PRODUCTION_DB)
            .filter(
                user_id__in=active_user_ids,
                changed_at__gte=restore_since,
                from_status=UserCommunityStatus.STATUS_ON_LEAVE,
            )
            .exclude(to_status=UserCommunityStatus.STATUS_ON_LEAVE)
            .order_by("user_id", "-changed_at")
            .values_list("user_id", "changed_at")
        ):
            if user_id not in restored_at_by_user:
                restored_at_by_user[user_id] = changed_at

    members = []
    for user_id in active_user_ids:
        username = username_by_id.get(user_id)
        if not username:
            continue
        char_ids = eve_ids_by_user.get(user_id, [])
        fleets = len(fleets_by_user.get(user_id, ()))
        if max_fleets is not None and fleets >= max_fleets:
            continue
        voice_min = voice_by_username.get(username, 0)
        restored_at = restored_at_by_user.get(user_id)
        members.append(
            {
                "username": username,
                "primary_character": primary_by_user.get(user_id),
                "previous_status": status_by_user.get(
                    user_id, UserCommunityStatus.STATUS_ACTIVE
                ),
                "linked_character_count": len(char_ids),
                "fleets": fleets,
                "kills": sum(kills_by_char.get(cid, 0) for cid in char_ids),
                "voice_minutes": voice_min,
                "voice_hours": round(voice_min / 60, 1),
                "restored_from_leave_at": (
                    restored_at.strftime("%Y-%m-%d") if restored_at else None
                ),
            }
        )

    members.sort(key=lambda m: (m["fleets"], m["kills"], m["voice_minutes"]))

    return {
        "as_of": now.strftime("%Y-%m-%d"),
        "window_days": days,
        "affiliation": affiliation_name,
        "community_status": "active",
        "member_count": len(members),
        "members": members,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Alliance member fleet/kill/voice activity"
    )
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout")
    parser.add_argument("--days", type=int, default=90, help="Lookback window")
    parser.add_argument(
        "--affiliation",
        default="Alliance",
        help="AffiliationType.name to include",
    )
    parser.add_argument(
        "--max-fleets",
        type=int,
        default=None,
        help="Only include members with fewer than this many fleets",
    )
    args = parser.parse_args()
    payload = fetch_activity(
        days=args.days,
        affiliation_name=args.affiliation,
        max_fleets=args.max_fleets,
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
