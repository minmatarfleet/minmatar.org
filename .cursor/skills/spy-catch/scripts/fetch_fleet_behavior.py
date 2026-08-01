#!/usr/bin/env python3
"""
Fetch Alliance fleet-behavior scorecards for spy-catch playbook.

Usage (from repo root):
  cd backend && pipenv run python ../.cursor/skills/spy-catch/scripts/fetch_fleet_behavior.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_DIR = REPO_ROOT / "backend"
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.json"

sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

import django

django.setup()

from django.contrib.auth.models import User
from django.utils import timezone

from discord.models import DiscordChannelActivityRecord
from eveonline.models import EveCharacter, EvePlayer
from fittings.models import EveDoctrineFitting
from fleets.models import EveFleetInstanceMember
from groups.models import UserAffiliation, UserCommunityStatus

PRODUCTION_DB = "production_readonly"


def time_region(dt: datetime) -> str:
    hour = dt.hour
    if hour in (22, 23, 0, 1, 2, 3, 4):
        return "US"
    if hour in (5, 6, 7, 8, 9):
        return "US_AP"
    if hour in (10, 11, 12, 13, 14):
        return "AP"
    if hour in (15, 16, 17, 18, 19):
        return "EU"
    if hour in (20, 21):
        return "EU_US"
    return "??"


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _as_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.utc)
    return dt


def _minutes(delta: timedelta) -> float:
    return max(delta.total_seconds() / 60.0, 0.0)


def _pct(n: int, d: int) -> float | None:
    if d <= 0:
        return None
    return round(n / d, 3)


def _top_share(counter: Counter) -> tuple[str | None, int, float | None]:
    if not counter:
        return None, 0, None
    key, count = counter.most_common(1)[0]
    total = sum(counter.values())
    return key, count, _pct(count, total)


def _voice_minutes_in_window(
    events: list[tuple[datetime, int]],
    start: datetime,
    end: datetime,
) -> int:
    total = 0
    for created_on, qty in events:
        if start <= created_on <= end:
            total += qty
    return total


def fetch_fleet_behavior(
    *,
    days: int,
    min_fleets: int,
    affiliation_name: str,
    config: dict,
    candidates_only: bool,
) -> dict:
    now = timezone.now()
    since = now - timedelta(days=days)

    long_fleet_minutes = float(config["long_fleet_minutes"])
    early_share = float(config["early_exit_max_presence_share"])
    early_max_min = float(config["early_exit_max_presence_minutes"])
    low_effort_ids = set(config["low_effort_ship_type_ids"])
    prefilter = config["prefilter"]
    exempt_group_names = list(config.get("exempt_groups", []))

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

    exempt_user_ids: set[int] = set()
    if exempt_group_names and active_user_ids:
        exempt_user_ids.update(
            User.objects.using(PRODUCTION_DB)
            .filter(
                id__in=active_user_ids,
                groups__name__in=exempt_group_names,
            )
            .values_list("id", flat=True)
            .distinct()
        )

    players = {
        ep.user_id: ep
        for ep in (
            EvePlayer.objects.using(PRODUCTION_DB)
            .filter(user_id__in=active_user_ids)
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

    doctrine_ships: dict[int, set[int]] = defaultdict(set)
    for doctrine_id, ship_id in (
        EveDoctrineFitting.objects.using(PRODUCTION_DB)
        .select_related("fitting")
        .values_list("doctrine_id", "fitting__ship_id")
    ):
        if ship_id is not None:
            doctrine_ships[doctrine_id].add(ship_id)

    members_by_user: dict[int, list[EveFleetInstanceMember]] = defaultdict(list)
    if all_eve_ids:
        qs = (
            EveFleetInstanceMember.objects.using(PRODUCTION_DB)
            .filter(
                character_id__in=all_eve_ids,
                eve_fleet_instance__start_time__gte=since,
            )
            .select_related(
                "eve_fleet_instance",
                "eve_fleet_instance__eve_fleet",
                "eve_fleet_instance__eve_fleet__audience",
                "eve_fleet_instance__eve_fleet__doctrine",
                "eve_fleet_instance__eve_fleet__created_by",
            )
        )
        for member in qs.iterator(chunk_size=2000):
            uid = user_by_eve.get(member.character_id)
            if uid is not None:
                members_by_user[uid].append(member)

    usernames = list(username_by_id.values())
    voice_events: dict[str, list[tuple[datetime, int]]] = defaultdict(list)
    if usernames:
        for username, created_on, quantity in (
            DiscordChannelActivityRecord.objects.using(PRODUCTION_DB)
            .filter(
                username__in=usernames,
                activity_type="voice_minute",
                created_on__gte=since,
            )
            .values_list("username", "created_on", "quantity")
            .iterator(chunk_size=5000)
        ):
            voice_events[username].append(
                (_as_aware(created_on), int(quantity or 0))
            )

    members_out: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    thin = 0
    exempt_count = 0

    for user_id in active_user_ids:
        username = username_by_id.get(user_id)
        if not username:
            continue

        player = players.get(user_id)
        primary = (
            player.primary_character.character_name
            if player and player.primary_character
            else None
        )
        prime_time = player.prime_time if player else None
        is_exempt = user_id in exempt_user_ids
        if is_exempt:
            exempt_count += 1

        attendances = members_by_user.get(user_id, [])
        # One row per fleet instance (prefer longest presence if multi-char)
        by_instance: dict[int, EveFleetInstanceMember] = {}
        for m in attendances:
            inst_id = m.eve_fleet_instance_id
            prev = by_instance.get(inst_id)
            if prev is None:
                by_instance[inst_id] = m
                continue
            prev_end = _as_aware(prev.updated_at) or _as_aware(prev.join_time)
            cur_end = _as_aware(m.updated_at) or _as_aware(m.join_time)
            prev_start = _as_aware(prev.join_time)
            cur_start = _as_aware(m.join_time)
            prev_presence = (
                _minutes(prev_end - prev_start)
                if prev_end and prev_start
                else 0
            )
            cur_presence = (
                _minutes(cur_end - cur_start) if cur_end and cur_start else 0
            )
            if cur_presence >= prev_presence:
                by_instance[inst_id] = m

        evidence_rows: list[dict[str, Any]] = []
        fc_counter: Counter = Counter()
        audience_counter: Counter = Counter()
        type_counter: Counter = Counter()
        region_counter: Counter = Counter()

        doctrine_fleets = 0
        doctrine_match = 0
        low_effort = 0
        early_exit = 0
        early_exit_docked = 0
        early_eligible = 0
        no_voice = 0
        voice_eligible = 0
        docked_final = 0

        for member in sorted(
            by_instance.values(),
            key=lambda m: m.eve_fleet_instance.start_time or now,
        ):
            instance = member.eve_fleet_instance
            fleet = instance.eve_fleet
            start = _as_aware(instance.start_time) or _as_aware(fleet.start_time)
            end = _as_aware(instance.end_time) or _as_aware(
                instance.last_updated
            )
            if start is None:
                continue
            if end is None or end < start:
                end = start + timedelta(minutes=long_fleet_minutes)

            join = _as_aware(member.join_time) or start
            last_seen = _as_aware(member.updated_at) or join
            if last_seen < join:
                last_seen = join

            instance_minutes = _minutes(end - start)
            presence_minutes = _minutes(last_seen - join)
            # Cap presence at instance end
            if last_seen > end:
                presence_minutes = _minutes(end - join)
                last_seen = end
            presence_share = (
                presence_minutes / instance_minutes
                if instance_minutes > 0
                else 1.0
            )

            fc_name = (
                fleet.created_by.username if fleet.created_by_id else None
            )
            audience_name = fleet.audience.name if fleet.audience_id else None
            fleet_type = fleet.type
            region = time_region(start)
            doctrine_id = fleet.doctrine_id
            doctrine_name = fleet.doctrine.name if fleet.doctrine_id else None
            hull_ids = doctrine_ships.get(doctrine_id, set()) if doctrine_id else set()

            # Final hull only (snapshots exist but skip N+1 for this pull)
            ship_id = member.ship_type_id

            in_doctrine = None
            if doctrine_id and hull_ids:
                doctrine_fleets += 1
                in_doctrine = ship_id in hull_ids
                if in_doctrine:
                    doctrine_match += 1

            is_low_effort = ship_id in low_effort_ids
            # Capsule after a long stay is usually podded, not "brought a capsule".
            if ship_id == 670 and presence_minutes >= 30:
                is_low_effort = False
            if is_low_effort:
                low_effort += 1

            docked = member.station_id is not None
            if docked:
                docked_final += 1

            is_early = False
            if instance_minutes >= long_fleet_minutes:
                early_eligible += 1
                # Prefer absolute short presence ("left before undock") over
                # share-of-very-long-fleet (hour in a 4h strat is not EarlyExit).
                is_early = presence_minutes <= early_max_min or (
                    presence_share <= early_share
                    and presence_minutes <= max(early_max_min * 2, 30)
                )
                if is_early:
                    early_exit += 1
                    if docked:
                        early_exit_docked += 1

            voice_min = 0
            if instance_minutes >= long_fleet_minutes:
                voice_eligible += 1
                voice_min = _voice_minutes_in_window(
                    voice_events.get(username, []), start, end
                )
                if voice_min <= 0:
                    no_voice += 1

            if fc_name:
                fc_counter[fc_name] += 1
            if audience_name:
                audience_counter[audience_name] += 1
            if fleet_type:
                type_counter[fleet_type] += 1
            region_counter[region] += 1

            evidence_rows.append(
                {
                    "fleet_id": fleet.id,
                    "instance_id": instance.id,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "time_region": region,
                    "type": fleet_type,
                    "audience": audience_name,
                    "doctrine_id": doctrine_id,
                    "doctrine_name": doctrine_name,
                    "fc": fc_name,
                    "objective": (fleet.objective or "")[:120] or None,
                    "character_id": member.character_id,
                    "character_name": member.character_name,
                    "ship_type_id": member.ship_type_id,
                    "ship_name": member.ship_name,
                    "in_doctrine": in_doctrine,
                    "low_effort": is_low_effort,
                    "join_time": join.isoformat(),
                    "last_seen": last_seen.isoformat(),
                    "presence_minutes": round(presence_minutes, 1),
                    "instance_minutes": round(instance_minutes, 1),
                    "presence_share": round(presence_share, 3),
                    "early_exit": is_early,
                    "docked": docked,
                    "voice_minutes": voice_min,
                }
            )

        fleet_count = len(evidence_rows)
        if fleet_count < min_fleets:
            thin += 1
            if candidates_only:
                continue

        top_fc, top_fc_n, top_fc_share = _top_share(fc_counter)
        top_aud, top_aud_n, top_aud_share = _top_share(audience_counter)
        top_type, top_type_n, top_type_share = _top_share(type_counter)
        top_region, top_region_n, top_region_share = _top_share(region_counter)

        doctrine_rate = _pct(doctrine_match, doctrine_fleets)
        low_effort_rate = _pct(low_effort, fleet_count)
        early_rate = _pct(early_exit, early_eligible)
        early_docked_rate = _pct(early_exit_docked, early_eligible)
        no_voice_rate = _pct(no_voice, voice_eligible)
        docked_rate = _pct(docked_final, fleet_count)

        flags: list[str] = []
        # SelectiveAttend: FC concentration only (single Alliance audience is normal).
        if (
            top_fc_share is not None
            and top_fc_share >= prefilter["fc_concentration_min"]
            and fleet_count >= prefilter.get("fc_concentration_min_fleets", min_fleets)
        ):
            flags.append("SelectiveAttend")

        if (
            doctrine_fleets >= prefilter.get("doctrine_fleets_min", 5)
            and doctrine_rate is not None
            and doctrine_rate <= prefilter["doctrine_max_rate"]
        ):
            flags.append("LowEffortShip")
        elif (
            doctrine_fleets >= prefilter.get("doctrine_fleets_min", 5)
            and low_effort_rate is not None
            and low_effort_rate >= prefilter["low_effort_min_rate"]
        ):
            flags.append("LowEffortShip")

        if (
            early_eligible >= prefilter.get("early_exit_min_eligible", 6)
            and early_rate is not None
            and early_rate >= prefilter["early_exit_min_rate"]
        ):
            flags.append("EarlyExit")
        elif (
            early_eligible >= prefilter.get("early_exit_min_eligible", 6)
            and early_docked_rate is not None
            and early_docked_rate >= prefilter["early_exit_docked_min_rate"]
        ):
            flags.append("EarlyExit")

        # Voice is supporting only — attach if already flagged on a primary signal.
        primary_flags = [f for f in flags if f != "FleetNoVoice"]
        if (
            primary_flags
            and no_voice_rate is not None
            and voice_eligible >= prefilter.get("no_voice_min_eligible", 8)
            and no_voice_rate >= prefilter["no_voice_min_rate"]
        ):
            flags.append("FleetNoVoice")

        if (
            primary_flags
            and prime_time
            and top_region
            and top_region_share
            and top_region_share >= 0.85
            and top_region not in prime_time
            and prime_time not in top_region
        ):
            flags.append("TzSkew")

        # Candidate only on primary fleet-behavior signals (not voice/TZ alone).
        is_candidate = (
            bool(primary_flags)
            and not is_exempt
            and fleet_count >= min_fleets
        )

        row = {
            "user_id": user_id,
            "username": username,
            "primary": primary,
            "prime_time": prime_time,
            "exempt": is_exempt,
            "exempt_groups": exempt_group_names if is_exempt else [],
            "fleets": fleet_count,
            "doctrine_fleets": doctrine_fleets,
            "doctrine_match": doctrine_match,
            "doctrine_rate": doctrine_rate,
            "low_effort": low_effort,
            "low_effort_rate": low_effort_rate,
            "early_eligible": early_eligible,
            "early_exit": early_exit,
            "early_exit_docked": early_exit_docked,
            "early_exit_rate": early_rate,
            "early_exit_docked_rate": early_docked_rate,
            "voice_eligible": voice_eligible,
            "no_voice": no_voice,
            "no_voice_rate": no_voice_rate,
            "docked_final": docked_final,
            "docked_rate": docked_rate,
            "top_fc": top_fc,
            "top_fc_count": top_fc_n,
            "top_fc_share": top_fc_share,
            "top_audience": top_aud,
            "top_audience_count": top_aud_n,
            "top_audience_share": top_aud_share,
            "top_type": top_type,
            "top_type_share": top_type_share,
            "top_time_region": top_region,
            "top_time_region_share": top_region_share,
            "flags": flags,
            "evidence": evidence_rows,
        }

        members_out.append(row)
        if is_candidate:
            candidates.append(row)

    members_out.sort(key=lambda r: (-len(r["flags"]), -r["fleets"], r["username"]))
    candidates.sort(key=lambda r: (-len(r["flags"]), -r["fleets"], r["username"]))

    payload = {
        "fetched_at": now.isoformat(),
        "days": days,
        "min_fleets": min_fleets,
        "affiliation": affiliation_name,
        "active_users": len(active_user_ids),
        "exempt_users": exempt_count,
        "thin_samples": thin,
        "candidate_count": len(candidates),
        "config": {
            "long_fleet_minutes": long_fleet_minutes,
            "early_exit_max_presence_share": early_share,
            "early_exit_max_presence_minutes": early_max_min,
            "prefilter": prefilter,
        },
        "candidates": candidates,
    }
    if not candidates_only:
        payload["members"] = members_out
    return payload


def main() -> None:
    config = load_config()
    parser = argparse.ArgumentParser(
        description="Fetch fleet-behavior scorecards for spy-catch"
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument(
        "--days",
        type=int,
        default=config.get("days", 90),
        help="Lookback days",
    )
    parser.add_argument(
        "--min-fleets",
        type=int,
        default=config.get("min_fleets", 5),
        help="Minimum tracked fleets to evaluate",
    )
    parser.add_argument(
        "--affiliation",
        default=config.get("affiliation", "Alliance"),
        help="AffiliationType.name",
    )
    parser.add_argument(
        "--all-members",
        action="store_true",
        help="Include non-candidate members in JSON (large)",
    )
    args = parser.parse_args()

    result = fetch_fleet_behavior(
        days=args.days,
        min_fleets=args.min_fleets,
        affiliation_name=args.affiliation,
        config=config,
        candidates_only=not args.all_members,
    )

    if args.json:
        # Trim evidence on non-needed bulk; keep full evidence for candidates
        print(json.dumps(result, default=str))
    else:
        print(
            f"candidates={result['candidate_count']} "
            f"active={result['active_users']} "
            f"exempt={result['exempt_users']} "
            f"window={result['days']}d"
        )
        for c in result["candidates"][:30]:
            print(
                f"  {c['username']}: fleets={c['fleets']} "
                f"flags={','.join(c['flags']) or '-'} "
                f"early={c['early_exit']}/{c['early_eligible']} "
                f"doctrine={c['doctrine_match']}/{c['doctrine_fleets']}"
            )


if __name__ == "__main__":
    main()
