#!/usr/bin/env python3
"""
Fetch Minmatar Fleet Academy pilot roster with behavioral metrics (JSON).

Does NOT decide graduation or corp routing — the agent applies SKILL.md.

Usage (from repo root):
  cd backend && pipenv run python ../.cursor/skills/academy-graduation/scripts/fetch_academy_pilots.py --json

Or from this skill directory:
  cd backend && pipenv run python manage.py shell < /dev/null  # ensure venv
  pipenv run python ../.cursor/skills/academy-graduation/scripts/fetch_academy_pilots.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_DIR = REPO_ROOT / "backend"
SKILL_DIR = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

import django

django.setup()

from django.db import connections
from django.db.models import Count, F, Sum
from django.utils import timezone

from discord.models import DiscordChannelActivityRecord
from eveonline.models import EveCharacterKillmailAttacker
from fleets.models import EveFleetInstanceMember, EveFleetRoleVolunteer

DEFAULT_CONFIG = SKILL_DIR / "config.json"
PRODUCTION_DB = "production_readonly"


def load_config(path: Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def days_since(now, dt) -> int | None:
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return (now - dt).days


def gang_bucket(size: int) -> str:
    if size <= 10:
        return "small"
    if size <= 24:
        return "medium"
    if size <= 39:
        return "large"
    return "blob"


def fetch_pilots(config: dict) -> dict:
    academy_id = config["academy_corporation_id"]
    window_days = config.get("behavior_window_days", 90)
    migration_date = date.fromisoformat(config["migration_batch_date"])

    now = timezone.now()
    since = now - timedelta(days=window_days)
    since30 = now - timedelta(days=30)

    cursor = connections[PRODUCTION_DB].cursor()
    cursor.execute(
        """
        SELECT c.character_id, c.character_name, u.username, ep.prime_time,
               du.created_at, DATE(du.created_at), DATE(c.created_at)
        FROM eveonline_evecharacter c
        JOIN auth_user u ON c.user_id = u.id
        LEFT JOIN eveonline_eveplayer ep ON ep.user_id = u.id
        LEFT JOIN discord_discorduser du ON du.user_id = u.id
        WHERE c.corporation_id = %s
        ORDER BY c.character_name
        """,
        [academy_id],
    )
    rows = cursor.fetchall()
    pilots = []

    for (
        char_id,
        name,
        username,
        prime_time,
        discord_joined,
        du_date,
        cc_date,
    ) in rows:
        tenure_days = days_since(now, discord_joined)
        tenure_unreliable = du_date == migration_date or cc_date == migration_date

        cursor.execute(
            """
            SELECT SUM(skill_points) FROM eveonline_evecharacterskill
            WHERE character_id = (
                SELECT id FROM eveonline_evecharacter WHERE character_id = %s
            )
            """,
            [char_id],
        )
        sp_row = cursor.fetchone()
        sp = int(sp_row[0] or 0) if sp_row and sp_row[0] else 0
        sp_m = round(sp / 1_000_000, 1) if sp else 0.0

        voice_min = int(
            DiscordChannelActivityRecord.objects.using(PRODUCTION_DB)
            .filter(
                username=username,
                activity_type="voice_minute",
                created_on__gte=since,
            )
            .aggregate(total=Sum("quantity"))["total"]
            or 0
        )

        fleet_qs = (
            EveFleetInstanceMember.objects.using(PRODUCTION_DB)
            .filter(character_id=char_id, join_time__gte=since)
            .select_related("eve_fleet_instance__eve_fleet")
        )
        fleets_90d = fleet_qs.count()
        fleet_types: dict[str, int] = {}
        fleet_sizes: list[int] = []
        for member in fleet_qs:
            eve_fleet = (
                member.eve_fleet_instance.eve_fleet
                if member.eve_fleet_instance
                else None
            )
            fleet_type = eve_fleet.type if eve_fleet else "unknown"
            fleet_types[fleet_type] = fleet_types.get(fleet_type, 0) + 1
            fleet_sizes.append(
                EveFleetInstanceMember.objects.using(PRODUCTION_DB)
                .filter(eve_fleet_instance_id=member.eve_fleet_instance_id)
                .count()
            )
        avg_fleet_size = (
            round(sum(fleet_sizes) / len(fleet_sizes), 1) if fleet_sizes else None
        )

        volunteered_roles = list(
            EveFleetRoleVolunteer.objects.using(PRODUCTION_DB)
            .filter(character_id=char_id, eve_fleet__start_time__gte=since)
            .values_list("role", flat=True)
            .distinct()
        )

        kill_qs = (
            EveCharacterKillmailAttacker.objects.using(PRODUCTION_DB)
            .filter(character_id=char_id, killmail__killmail_time__gte=since)
            .exclude(character_id=F("killmail__victim_character_id"))
            .annotate(
                gang_size=Count(
                    "killmail__evecharacterkillmailattacker", distinct=True
                )
            )
        )
        gang_counts = {"small": 0, "medium": 0, "large": 0, "blob": 0}
        kills_90d = 0
        for kill in kill_qs:
            kills_90d += 1
            gang_counts[gang_bucket(kill.gang_size)] += 1

        kills_30d = (
            EveCharacterKillmailAttacker.objects.using(PRODUCTION_DB)
            .filter(character_id=char_id, killmail__killmail_time__gte=since30)
            .exclude(character_id=F("killmail__victim_character_id"))
            .count()
        )

        cursor.execute(
            """
            SELECT COUNT(*) FROM eveonline_evecharacterkillmail km
            JOIN eveonline_evecharacter ec ON km.character_id = ec.id
            WHERE ec.character_id = %s AND km.victim_character_id = %s
              AND km.killmail_time >= %s
            """,
            [char_id, char_id, since.strftime("%Y-%m-%d %H:%M:%S")],
        )
        losses_90d = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*) FROM eveonline_evecharacterindustryjob j
            JOIN eveonline_evecharacter ec ON j.character_id = ec.id
            WHERE ec.character_id = %s
            """,
            [char_id],
        )
        industry_jobs = cursor.fetchone()[0]

        pilots.append(
            {
                "character_name": name,
                "character_id": char_id,
                "username": username,
                "prime_time": prime_time,
                "sp_m": sp_m,
                "tenure_days": tenure_days,
                "tenure_unreliable": tenure_unreliable,
                "voice_minutes_90d": voice_min,
                "fleets_90d": fleets_90d,
                "fleet_types_90d": fleet_types,
                "avg_fleet_size": avg_fleet_size,
                "volunteered_roles_90d": volunteered_roles,
                "kills_30d": kills_30d,
                "kills_90d": kills_90d,
                "losses_90d": losses_90d,
                "gang_kills_90d": gang_counts,
                "industry_jobs": industry_jobs,
            }
        )

    return {
        "as_of": now.strftime("%Y-%m-%d"),
        "academy_corporation_id": academy_id,
        "behavior_window_days": window_days,
        "graduate_days": config.get("graduate_days", 180),
        "pilot_count": len(pilots),
        "pilots": pilots,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch L3ARN pilot behavioral data")
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Path to config.json",
    )
    args = parser.parse_args()
    config = load_config(args.config)
    payload = fetch_pilots(config)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
