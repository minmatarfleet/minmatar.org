"""Generate Providence campaign page data from production DB + zKillboard.

Combines EveFleetInstance participation (May–Oct 2024), scheduled fleet
counts, zKill monthly ISK in Providence, and optional killmail inference for
AAR-linked fleets without instance snapshots.

Usage (from backend/):
    pipenv run python scripts/generate_providence_campaign_data.py

Output:
    scripts/output/providence_campaign_data.json
    ../frontend/app/src/data/campaigns/providence.ts
"""
from __future__ import annotations

import json
import logging
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import django
import requests

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os_environ = __import__("os").environ
os_environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
django.setup()

from django.db.models import Count, F
from django.db.models.functions import TruncMonth
from django.utils import timezone as dj_timezone

from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
    EvePlayer,
)
from fleets.models import EveFleet, EveFleetInstance, EveFleetInstanceMember

logger = logging.getLogger(__name__)

READ_DB = "production_readonly"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
ZKILL_CACHE = OUTPUT_DIR / "providence_zkill_cache.json"
REPORT_PATH = OUTPUT_DIR / "fleet_aar_link_report.json"
FRONTEND_DATA = (
    REPO_ROOT / "frontend" / "app" / "src" / "data" / "campaigns" / "providence.ts"
)

PROVIDENCE_REGION_ID = 10000047
ALLIANCE_ID = 99011978
ZKILL_BASE = "https://zkillboard.com/api/"
USER_AGENT = "minmatar.org-providence-campaign/1.0 (https://minmatar.org)"
BR_RE = re.compile(r"https://br\.evetools\.org/(?:br/)?([a-f0-9]+)", re.I)

PERIOD_START = dj_timezone.make_aware(datetime(2024, 1, 1))
PERIOD_END = dj_timezone.make_aware(datetime(2025, 4, 1))

MONTH_LABELS = [
    "Jan 24",
    "Feb 24",
    "Mar 24",
    "Apr 24",
    "May 24",
    "Jun 24",
    "Jul 24",
    "Aug 24",
    "Sep 24",
    "Oct 24",
    "Nov 24",
    "Dec 24",
    "Jan 25",
    "Feb 25",
    "Mar 25",
]

# CVA, Absolute Honor, Providence holders, and RMC — not SEDIT/Vard/etc.
ENEMY_ALLIANCE_IDS = frozenset(
    {
        1988009451,  # Curatores Veritatis Alliance (CVA)
        99010240,  # The Curatores Veritatis Auxiliary
        99010386,  # Absolute Honor
        99010995,  # Empyrean Edict
        99012995,  # Dragon Riders Legion (RMC)
        99012827,  # Imperial Dragon Riders Legion
    }
)

CAMPAIGN_EXCLUDE_RE = re.compile(
    r"sedit|vard\b|aldodan|waifu|siseide|huola|imperium pet|snuffed|"
    r"mobile depot|angel\b|retribution|kamela|shipping in wolf|anka\b|"
    r"mining permit|bombing|training fleet|krabbing|kitchen accident",
    re.I,
)

CAMPAIGN_BEATS = [
    {"monthIndex": 0, "label": "FL33T declares war on CVA"},
    {"monthIndex": 0, "label": "RMC declares as CVA ally"},
    {"monthIndex": 0, "label": "RMC contracts AO"},
    {"monthIndex": 5, "label": "Providence attacks FL33T staging Fortizar"},
    {"monthIndex": 8, "label": "Shift to Pochven / Warzone"},
    {"monthIndex": 10, "label": "Return to Providence"},
    {"monthIndex": 13, "label": "RMC calls Imperium"},
]

HEADLINE_SEEDS = [
    {
        "title": "FL33T DECLARES WAR ON CVA",
        "url": "https://www.reddit.com/r/Eve/comments/190grzs/fl33t_celebrates_1_year_and_declares_war_on_cva/",
        "date": "2024-01-07",
        "category": "aar",
    },
    {
        "title": "20 DAYS IN PROVIDENCE",
        "url": "https://www.reddit.com/r/Eve/comments/19bcsz7/20_days_in_providence/",
        "date": "2024-01-20",
        "category": "aar",
    },
    {
        "title": "ABSOLUTE ORDER BAITED ON A FREE RAITARU",
        "url": "https://www.reddit.com/r/Eve/comments/1e332ss/aar_absolute_order_baited_on_a_free_raitaru/",
        "date": "2024-07-16",
        "category": "aar",
    },
    {
        "title": "400B DOWN IN PROVIDENCE",
        "url": "https://www.reddit.com/r/Eve/comments/1e8qqve/aar_400b_down_in_providence_no_moon_drills_in/",
        "date": "2024-07-21",
        "category": "aar",
    },
    {
        "title": "MINMIL BITES OFF MORE THAN THEY CAN CHEW",
        "url": "https://www.reddit.com/r/Eve/comments/1g8pcse/aar_minmil_bites_off_more_than_they_can_chew/",
        "date": "2024-10-21",
        "category": "aar",
    },
    {
        "title": "FL33T VS PROVIDENCE",
        "url": "https://www.reddit.com/r/Eve/comments/1g2xq0k/aar_fl33t_vs_providence/",
        "date": "2024-10-06",
        "category": "aar",
    },
]

HEADLINE_AAR_BACKGROUNDS = [
    "/images/combatlog-tile-background.webp",
    "/images/dread-card.jpg",
]


@dataclass
class ZkbRow:
    killmail_time: datetime
    total_value: float


def _zkill_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def _parse_zkill_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def _fetch_zkill_month(
    session: requests.Session,
    *,
    kind: str,
    year: int,
    month: int,
) -> list[ZkbRow]:
    rows: list[ZkbRow] = []
    page = 1

    while True:
        path = (
            f"{kind}/allianceID/{ALLIANCE_ID}/regionID/{PROVIDENCE_REGION_ID}/"
            f"year/{year}/month/{month:02d}/page/{page}/"
        )
        url = urljoin(ZKILL_BASE, path)
        response = session.get(url, timeout=60)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("error"):
            raise RuntimeError(payload["error"])
        if not payload:
            break

        for row in payload:
            zkb = row.get("zkb", {})
            rows.append(
                ZkbRow(
                    killmail_time=_parse_zkill_time(zkb.get("killmail_time"))
                    or datetime(year, month, 1, tzinfo=timezone.utc),
                    total_value=float(zkb.get("totalValue", 0) or 0),
                )
            )

        if len(payload) < 200:
            break
        page += 1
        time.sleep(1.1)

    return rows


def _aar_thread_names_by_fleet() -> dict[int, str]:
    if not REPORT_PATH.is_file():
        return {}
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    return {
        int(match["fleet_id"]): match.get("thread_name", "")
        for match in report.get("matches", [])
    }


def _fleet_campaign_text(fleet: EveFleet, aar_threads: dict[int, str]) -> str:
    return f"{aar_threads.get(fleet.id, '')} {fleet.description or ''}"


def _is_in_scope_fleet(fleet: EveFleet, aar_threads: dict[int, str]) -> bool:
    """Campaign period fleets, excluding SEDIT/Vard/etc. — not keyword-gated."""
    return not CAMPAIGN_EXCLUDE_RE.search(_fleet_campaign_text(fleet, aar_threads))


def _in_scope_fleet_ids() -> set[int]:
    aar_threads = _aar_thread_names_by_fleet()
    return {
        fleet.id
        for fleet in EveFleet.objects.using(READ_DB).filter(
            start_time__gte=PERIOD_START, start_time__lt=PERIOD_END
        )
        if _is_in_scope_fleet(fleet, aar_threads)
    }


def _fc_instance_counts(
    fleet_ids: set[int], char_to_user: dict[int, int]
) -> Counter[int]:
    """Count fleets commanded per player — FC role when tracked, else scheduler."""
    counts: Counter[int] = Counter()
    instances = list(
        EveFleetInstance.objects.using(READ_DB)
        .filter(eve_fleet_id__in=fleet_ids)
        .values_list("id", "eve_fleet_id", "eve_fleet__created_by_id")
    )
    instanced_fleet_ids: set[int] = set()
    if instances:
        instance_ids = [row[0] for row in instances]
        commander_by_instance: dict[int, int] = {}
        for instance_id, character_id in (
            EveFleetInstanceMember.objects.using(READ_DB)
            .filter(eve_fleet_instance_id__in=instance_ids, role="fleet_commander")
            .order_by("eve_fleet_instance_id", "id")
            .values_list("eve_fleet_instance_id", "character_id")
        ):
            commander_by_instance.setdefault(instance_id, character_id)

        for instance_id, fleet_id, created_by_id in instances:
            instanced_fleet_ids.add(fleet_id)
            commander_id = commander_by_instance.get(instance_id)
            user_id = (
                char_to_user.get(commander_id) if commander_id else created_by_id
            )
            if user_id:
                counts[user_id] += 1

    for fleet in (
        EveFleet.objects.using(READ_DB)
        .filter(id__in=fleet_ids - instanced_fleet_ids)
        .exclude(created_by_id__isnull=True)
    ):
        counts[fleet.created_by_id] += 1

    return counts


def _load_or_fetch_zkill_monthly() -> tuple[list[float], list[float]]:
    month_count = len(MONTH_LABELS)
    if ZKILL_CACHE.is_file():
        cached = json.loads(ZKILL_CACHE.read_text(encoding="utf-8"))
        if cached.get("version") == 2:
            return (
                cached["destroyed"][:month_count],
                cached["lost"][:month_count],
            )

    session = _zkill_session()
    destroyed: list[float] = []
    lost: list[float] = []

    for year, month in [
        (2024, 1),
        (2024, 2),
        (2024, 3),
        (2024, 4),
        (2024, 5),
        (2024, 6),
        (2024, 7),
        (2024, 8),
        (2024, 9),
        (2024, 10),
        (2024, 11),
        (2024, 12),
        (2025, 1),
        (2025, 2),
        (2025, 3),
    ]:
        logger.info("zKill Providence %04d-%02d kills...", year, month)
        kill_rows = _fetch_zkill_month(
            session, kind="kills", year=year, month=month
        )
        destroyed.append(sum(row.total_value for row in kill_rows))
        time.sleep(1.1)
        logger.info("zKill Providence %04d-%02d losses...", year, month)
        loss_rows = _fetch_zkill_month(
            session, kind="losses", year=year, month=month
        )
        lost.append(sum(row.total_value for row in loss_rows))
        time.sleep(1.1)

    ZKILL_CACHE.write_text(
        json.dumps(
            {
                "version": 2,
                "destroyed": destroyed,
                "lost": lost,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return destroyed, lost


def _character_name(character_id: int) -> str:
    char = (
        EveCharacter.objects.using(READ_DB)
        .filter(character_id=character_id)
        .only("character_name")
        .first()
    )
    return char.character_name if char else f"Character {character_id}"


def _user_primary_character_id(user_id: int) -> int | None:
    player = EvePlayer.objects.using(READ_DB).filter(user_id=user_id).first()
    if player and player.primary_character_id:
        return player.primary_character.character_id
    character = (
        EveCharacter.objects.using(READ_DB).filter(user_id=user_id).order_by("id").first()
    )
    return character.character_id if character else None


def _monthly_fleets(fleet_ids: set[int]) -> list[int]:
    fleets = EveFleet.objects.using(READ_DB).filter(id__in=fleet_ids)
    by_month: dict[int, int] = {index: 0 for index in range(len(MONTH_LABELS))}
    for row in fleets.annotate(m=TruncMonth("start_time")).values("m").annotate(
        c=Count("id")
    ):
        index = (row["m"].year - 2024) * 12 + row["m"].month - 1
        if 0 <= index < len(MONTH_LABELS):
            by_month[index] = row["c"]
    return [by_month[index] for index in range(len(MONTH_LABELS))]


def _providence_system_ids() -> set[int]:
    response = requests.get(
        f"https://esi.evetech.net/latest/universe/regions/{PROVIDENCE_REGION_ID}/",
        timeout=30,
    )
    response.raise_for_status()
    return set(response.json()["constellations"])


def _load_region_system_ids() -> set[int]:
    constellation_ids = _providence_system_ids()
    system_ids: set[int] = set()
    for constellation_id in constellation_ids:
        response = requests.get(
            f"https://esi.evetech.net/latest/universe/constellations/{constellation_id}/",
            timeout=30,
        )
        response.raise_for_status()
        system_ids.update(response.json()["systems"])
        time.sleep(0.05)
    return system_ids


def _infer_pilots_from_killmails(
    fleet_ids: set[int],
    region_system_ids: set[int],
    char_to_user: dict[int, int],
) -> dict[int, set[int]]:
    """Map user_id -> fleet_ids inferred from Providence killmail attackers."""
    inferred: dict[int, set[int]] = defaultdict(set)
    alliance_ids = set(
        EveAlliance.objects.using(READ_DB).values_list("alliance_id", flat=True)
    )
    alliance_char_ids = set(
        EveCharacter.objects.using(READ_DB)
        .filter(alliance_id__in=alliance_ids)
        .values_list("character_id", flat=True)
    )

    fleets = {
        fleet.id: fleet
        for fleet in EveFleet.objects.using(READ_DB).filter(id__in=fleet_ids)
    }
    instanced_fleet_ids = set(
        EveFleetInstance.objects.using(READ_DB)
        .filter(eve_fleet_id__in=fleet_ids)
        .values_list("eve_fleet_id", flat=True)
    )

    for fleet_id, fleet in fleets.items():
        if fleet_id in instanced_fleet_ids:
            continue
        window_end = fleet.start_time + dj_timezone.timedelta(hours=6)
        kill_ids = EveCharacterKillmail.objects.using(READ_DB).filter(
            killmail_time__gte=fleet.start_time,
            killmail_time__lt=window_end,
            solar_system_id__in=region_system_ids,
        ).values_list("id", flat=True)
        if not kill_ids:
            continue
        attacker_ids = (
            EveCharacterKillmailAttacker.objects.using(READ_DB)
            .filter(
                killmail_id__in=kill_ids,
                character_id__in=alliance_char_ids,
            )
            .exclude(character_id=F("killmail__victim_character_id"))
            .values_list("character_id", flat=True)
            .distinct()
        )
        for character_id in attacker_ids:
            user_id = char_to_user.get(character_id)
            if user_id:
                inferred[user_id].add(fleet_id)

    return inferred


def _participation_stats(in_scope_fleet_ids: set[int]) -> dict:
    instances = EveFleetInstance.objects.using(READ_DB).filter(
        eve_fleet_id__in=in_scope_fleet_ids,
    )
    members = EveFleetInstanceMember.objects.using(READ_DB).filter(
        eve_fleet_instance__in=instances
    )

    char_to_user = {
        int(row["character_id"]): int(row["user_id"])
        for row in EveCharacter.objects.using(READ_DB)
        .exclude(user_id__isnull=True)
        .values("character_id", "user_id")
    }

    pilot_instances: dict[int, set[int]] = defaultdict(set)
    pilot_characters: dict[int, set[int]] = defaultdict(set)
    for member in members.iterator():
        user_id = char_to_user.get(member.character_id)
        if not user_id:
            continue
        pilot_instances[user_id].add(member.eve_fleet_instance_id)
        pilot_characters[user_id].add(member.character_id)

    aar_linked_fleet_ids = {
        fleet_id
        for fleet_id in in_scope_fleet_ids
        if EveFleet.objects.using(READ_DB)
        .filter(id=fleet_id)
        .exclude(aar_link__isnull=True)
        .exclude(aar_link="")
        .exists()
    }
    region_system_ids = _load_region_system_ids()
    inferred = _infer_pilots_from_killmails(
        aar_linked_fleet_ids, region_system_ids, char_to_user
    )
    for user_id, inferred_fleet_ids in inferred.items():
        for fleet_id in inferred_fleet_ids:
            pilot_instances[user_id].add(-fleet_id)

    fc_instance_counts = _fc_instance_counts(in_scope_fleet_ids, char_to_user)

    fc_scheduled_counts: Counter[int] = Counter()
    for row in (
        EveFleet.objects.using(READ_DB)
        .filter(id__in=in_scope_fleet_ids)
        .values("created_by_id")
        .annotate(c=Count("id"))
    ):
        if row["created_by_id"]:
            fc_scheduled_counts[row["created_by_id"]] += row["c"]

    fc_entries: list[dict] = []
    for user_id, count in fc_instance_counts.most_common():
        character_id = _user_primary_character_id(user_id)
        if not character_id:
            continue
        fc_entries.append(
            {
                "characterId": character_id,
                "name": _character_name(character_id),
                "fleetCount": count,
                "scheduledFleetCount": fc_scheduled_counts.get(user_id, 0),
            }
        )

    top_fc_character_ids = {entry["characterId"] for entry in fc_entries[:4]}
    pilot_entries = []
    for user_id, instance_ids in sorted(
        pilot_instances.items(), key=lambda item: len(item[1]), reverse=True
    ):
        character_id = _user_primary_character_id(user_id)
        if not character_id or character_id in top_fc_character_ids:
            continue
        pilot_entries.append(
            {
                "characterId": character_id,
                "name": _character_name(character_id),
                "fleetCount": len(instance_ids),
                "altCount": len(pilot_characters[user_id]),
            }
        )

    alliance_user_ids = set(
        EveCharacter.objects.using(READ_DB)
        .filter(alliance_id=ALLIANCE_ID)
        .exclude(user_id__isnull=True)
        .values_list("user_id", flat=True)
        .distinct()
    )
    fleet_pilots = len(pilot_instances)
    fleet_characters = len(
        {char for chars in pilot_characters.values() for char in chars}
    )
    participation_pct = min(
        100,
        round(100 * fleet_pilots / len(alliance_user_ids))
        if alliance_user_ids
        else 0,
    )

    top_commanders = fc_entries[:4]
    other_commanders = fc_entries[4:]
    other_fleet_count = sum(entry["fleetCount"] for entry in other_commanders)

    return {
        "fleet_pilots": fleet_pilots,
        "fleet_characters": fleet_characters,
        "participation_pct": participation_pct,
        "inferred_fleet_links": sum(len(v) for v in inferred.values()),
        "top_commanders": top_commanders,
        "other_commanders": {
            "fleetCount": other_fleet_count,
            "commanders": [
                {
                    "characterId": entry["characterId"],
                    "name": entry["name"],
                    "fleetCount": entry["fleetCount"],
                }
                for entry in other_commanders
            ],
        },
        "top_pilots": pilot_entries[:5],
        "instance_count": instances.count(),
        "aar_linked_fleets": len(aar_linked_fleet_ids),
        "campaign_fleet_ids": len(in_scope_fleet_ids),
    }


def _format_ts_number(value: float | int) -> str:
    if isinstance(value, float):
        return f"{value:.0f}" if value.is_integer() else str(value)
    return f"{value:_}".replace("_", "_")


def _render_providence_ts(
    *,
    fleets_monthly: list[int],
    isk_destroyed_monthly: list[float],
    isk_lost_monthly: list[float],
    participation: dict,
) -> str:
    gross_kills = int(sum(isk_destroyed_monthly))
    gross_losses = int(sum(isk_lost_monthly))
    total_fleets = sum(fleets_monthly)

    def fleet_commander_lines(entries: list[dict], indent: str = "    ") -> str:
        lines = []
        for entry in entries:
            lines.append(
                f"{indent}{{ characterId: {entry['characterId']:_}, "
                f"name: {json.dumps(entry['name'])}, "
                f"fleetCount: {entry['fleetCount']} }},"
            )
        return "\n".join(lines)

    headline_lines = []
    for index, seed in enumerate(HEADLINE_SEEDS):
        headline_lines.append(
            "    {\n"
            f"        title: {json.dumps(seed['title'])},\n"
            f"        url: {json.dumps(seed['url'])},\n"
            f"        date: {json.dumps(seed['date'])},\n"
            f"        category: {json.dumps(seed['category'])},\n"
            f"        backgroundImage: HEADLINE_AAR_BACKGROUNDS[{index % 2}],\n"
            "        upvotes: 0,\n"
            "        comments: 0,\n"
            '        views: "—",\n'
            "    },"
        )

    beats_lines = [
        f"    {{ monthIndex: {beat['monthIndex']}, label: {json.dumps(beat['label'])} }},"
        for beat in CAMPAIGN_BEATS
    ]

    other_commander_lines = fleet_commander_lines(
        participation["other_commanders"]["commanders"]
    )
    top_pilot_lines = fleet_commander_lines(participation["top_pilots"])

    return f"""export const MONTHS = {json.dumps(MONTH_LABELS)} as const

export const FLEETS_MONTHLY = {json.dumps(fleets_monthly)}

export const CAMPAIGN_BEATS = [
{chr(10).join(beats_lines)}
] as const

export const ISK_DESTROYED_MONTHLY = [
{", ".join(str(int(v)) for v in isk_destroyed_monthly)}
]

export const ISK_LOST_MONTHLY = [
{", ".join(str(int(v)) for v in isk_lost_monthly)}
]

export const PERIOD_PROVIDENCE_ISK_KILLS = {gross_kills:_}
export const PERIOD_PROVIDENCE_ISK_LOSSES = {gross_losses:_}
export const PERIOD_CAMPAIGN_FLEETS = {total_fleets}

export type FleetCommanderEntry =
    | {{
          characterId: number
          name: string
          fleetCount: number
      }}
    | {{
          characterId: null
          name: string
          fleetCount: number
          isAggregate: true
      }}

/** Top FCs by fleets commanded (in-game FC role, or scheduled when untracked) · Jan 2024 – Mar 2025. */
export const TOP_FLEET_COMMANDERS: readonly FleetCommanderEntry[] = [
{fleet_commander_lines(participation['top_commanders'])}
    {{
        characterId: null,
        name: 'Other commanders',
        fleetCount: {participation['other_commanders']['fleetCount']},
        isAggregate: true,
    }},
]

export const OTHER_FLEET_COMMANDERS = {{
    fleetCount: {participation['other_commanders']['fleetCount']},
    commanders: [
{other_commander_lines}
    ],
}} as const

/** Top pilots by player · distinct fleet instances across alts · excludes TOP_FLEET_COMMANDERS · Jan 2024 – Mar 2025. */
export const TOP_FLEET_PILOTS = [
{top_pilot_lines}
] as const

export const FLEET_PILOTS = {participation['fleet_pilots']}
export const FLEET_CHARACTERS = {participation['fleet_characters']}
export const FLEET_PARTICIPATION_PCT = {participation['participation_pct']}

export const GROSS_ISK_KILLS = PERIOD_PROVIDENCE_ISK_KILLS
export const GROSS_ISK_LOSSES = PERIOD_PROVIDENCE_ISK_LOSSES
export const CAMPAIGN_ISK_DESTROYED = GROSS_ISK_KILLS

export const COVER_IMAGE = '/images/dread-card.jpg'

export type CampaignHeadlineCategory = 'aar' | 'industry'

export const HEADLINE_AAR_BACKGROUNDS = {json.dumps(HEADLINE_AAR_BACKGROUNDS)} as const

export type CampaignHeadline = {{
    title: string
    url: string
    date: string
    category: CampaignHeadlineCategory
    backgroundImage: string
    upvotes: number
    comments: number
    views: string | number
}}

/** u/BearThatCares · r/Eve Providence campaign AARs · Jan 2024 – Mar 2025. */
export const HEADLINES: readonly CampaignHeadline[] = [
{chr(10).join(headline_lines)}
] as const

export function toBillions(isk: number): number {{
    return Math.round((isk / 1_000_000_000) * 100) / 100
}}

export function formatIsk(isk: number): string {{
    if (isk >= 1_000_000_000_000) {{
        return `${{(isk / 1_000_000_000_000).toFixed(2)}}T`
    }}
    if (isk >= 1_000_000_000) {{
        return `${{(isk / 1_000_000_000).toFixed(1)}}B`
    }}
    if (isk >= 1_000_000) {{
        return `${{(isk / 1_000_000).toFixed(0)}}M`
    }}
    return `${{(isk / 1_000).toFixed(0)}}K`
}}

export type CampaignRowTone = 'info' | 'success' | 'warning' | 'danger' | undefined

export type CampaignTableRow = {{
    cells: [string, string] | [string, string, string]
    tone?: CampaignRowTone
}}
"""


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Resolving in-scope fleet IDs (excluding SEDIT/Vard/etc.)...")
    fleet_ids = _in_scope_fleet_ids()
    logger.info("In-scope fleets: %s", len(fleet_ids))

    logger.info("Computing monthly fleet counts...")
    fleets_monthly = _monthly_fleets(fleet_ids)

    logger.info("Fetching zKill monthly ISK (cached if available)...")
    isk_destroyed_monthly, isk_lost_monthly = _load_or_fetch_zkill_monthly()

    logger.info("Computing participation stats...")
    participation = _participation_stats(fleet_ids)

    report = {
        "period": {
            "start": PERIOD_START.isoformat(),
            "end": PERIOD_END.isoformat(),
        },
        "campaign_scope": {
            "enemy_alliance_ids": sorted(ENEMY_ALLIANCE_IDS),
            "in_scope_fleet_count": len(fleet_ids),
            "excludes": "SEDIT, Vard, Siseide, Huola, and other unrelated lowsec fights",
            "fc_counting": "in-game fleet_commander role when tracked; scheduler for pre-instance fleets",
        },
        "fleets_monthly": fleets_monthly,
        "isk_destroyed_monthly": [int(v) for v in isk_destroyed_monthly],
        "isk_lost_monthly": [int(v) for v in isk_lost_monthly],
        "participation": participation,
        "notes": {
            "instance_tracking_from": "2024-05-27",
            "aar_linked_fleets": participation["aar_linked_fleets"],
            "br_api_status": "archived BR battle endpoint returns 404; killmail inference used for non-instanced AAR-linked fleets",
        },
    }

    json_path = OUTPUT_DIR / "providence_campaign_data.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Wrote %s", json_path)

    ts_content = _render_providence_ts(
        fleets_monthly=fleets_monthly,
        isk_destroyed_monthly=isk_destroyed_monthly,
        isk_lost_monthly=isk_lost_monthly,
        participation=participation,
    )
    FRONTEND_DATA.parent.mkdir(parents=True, exist_ok=True)
    FRONTEND_DATA.write_text(ts_content, encoding="utf-8")
    logger.info("Wrote %s", FRONTEND_DATA)
    return 0


if __name__ == "__main__":
    sys.exit(main())
