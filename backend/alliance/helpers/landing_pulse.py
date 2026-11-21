"""
Public "heartbeat" for the new landing page (/landing-new).

Everything here runs 60 minutes behind real time, so nothing on the page
says where the alliance is right now. Kills name a region, never a system;
comms lines never name a channel; fleets appear only after they end.

The rollup is cached: the cheap 24-hour/7-day part for five minutes and the
30-day part (timezone chart, month moments) for an hour.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMinute
from django.utils import timezone

from app.cache import CachedRollup
from campaigns.models import CampaignSiteCompletion
from discord.models import DiscordChannelActivityRecord, DiscordUser
from eveonline.client import live_esi_allowed
from eveonline.constants import (
    AMARR_FACTION_ID,
    CALDARI_FACTION_ID,
    GALLENTE_FACTION_ID,
    MINMATAR_FACTION_ID,
    MINMATAR_FLEET_ALLIANCE_ID,
)
from eveonline.helpers.characters.identity import primary_characters_for_users
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCharacterIndustryJob,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
    EveCorporation,
    EveCorporationContract,
)
from eveuniverse.models import EveSolarSystem, EveType
from feed.helpers.eve_names import resolve_entity_names
from fleets.models import EveFleet, EveFleetInstance, EveFleetInstanceMember

logger = logging.getLogger(__name__)

DELAY = timedelta(minutes=60)
FAST = CachedRollup(
    key="alliance:landing_pulse:fast:v1",
    ttl=300,
    lock_key="alliance:landing_pulse:fast:lock",
    lock_ttl=60,
)
SLOW = CachedRollup(
    key="alliance:landing_pulse:slow:v1",
    ttl=3600,
    lock_key="alliance:landing_pulse:slow:lock",
    lock_ttl=120,
)

MAX_EVENTS = 60
# A voice gathering worth a line: at least this many pilots in one minute.
VOICE_MIN_PILOTS = 3
MANUFACTURING_ACTIVITY_ID = 1

FACTION_MILITIA_NAMES = {
    CALDARI_FACTION_ID: "the Caldari Militia",
    MINMATAR_FACTION_ID: "the Minmatar Militia",
    AMARR_FACTION_ID: "the Amarr Militia",
    GALLENTE_FACTION_ID: "the Gallente Militia",
    500010: "the Guristas",
    500011: "the Angel Cartel",
}

SITE_ACTIONS = {
    "complex": "captured a complex",
    "supply_cache": "ran a supply cache site",
}
DEFAULT_SITE_ACTION = "ran a warzone site"


@dataclass
class Event:
    occurred_at: datetime
    kind: str
    character_id: int | None
    action: str
    others: int = 0
    region: str = ""


# --------------------------------------------------------------------------
# Small lookups
# --------------------------------------------------------------------------


def _kills_q():
    """Killmails where the victim is not one of ours."""
    return Q(victim_alliance_id__isnull=True) | ~Q(
        victim_alliance_id=MINMATAR_FLEET_ALLIANCE_ID
    )


def _character_names(character_ids) -> dict[int, str]:
    ids = {int(c) for c in character_ids if c}
    if not ids:
        return {}
    return {
        cid: name
        for cid, name in EveCharacter.objects.filter(
            character_id__in=ids
        ).values_list("character_id", "character_name")
        if name
    }


def _entity_names(alliance_ids, corporation_ids) -> dict[int, str]:
    names: dict[int, str] = {}
    alliance_ids = {int(a) for a in alliance_ids if a}
    corporation_ids = {int(c) for c in corporation_ids if c}
    if alliance_ids:
        names.update(
            {
                aid: name
                for aid, name in EveAlliance.objects.filter(
                    alliance_id__in=alliance_ids
                ).values_list("alliance_id", "name")
                if name
            }
        )
    if corporation_ids:
        names.update(
            {
                cid: name
                for cid, name in EveCorporation.objects.filter(
                    corporation_id__in=corporation_ids
                ).values_list("corporation_id", "name")
                if name
            }
        )
    missing = (alliance_ids | corporation_ids) - names.keys()
    if missing and live_esi_allowed():
        try:
            names.update(
                {
                    k: v
                    for k, v in resolve_entity_names(missing).items()
                    if not v.startswith("Entity ")
                }
            )
        except Exception:  # pylint: disable=broad-except
            # Names are decoration: the line still reads "won a fight".
            logger.warning("Landing pulse name lookup failed", exc_info=True)
    return names


def _region_names_for_systems(system_ids) -> dict[int, str]:
    ids = {int(s) for s in system_ids if s}
    if not ids:
        return {}
    return {
        sid: region or ""
        for sid, region in EveSolarSystem.objects.filter(
            id__in=ids
        ).values_list("id", "eve_constellation__eve_region__name")
    }


def _type_names(type_ids) -> dict[int, str]:
    ids = {int(t) for t in type_ids if t}
    if not ids:
        return {}
    return dict(EveType.objects.filter(id__in=ids).values_list("id", "name"))


def _duration_words(seconds: float) -> str:
    minutes = int(round(seconds / 60))
    if minutes < 90:
        return f"{minutes} minutes"
    hours = round(minutes / 60 * 2) / 2
    if hours == int(hours):
        hours = int(hours)
    return f"{hours} hours"


# --------------------------------------------------------------------------
# Totals
# --------------------------------------------------------------------------


def _distinct_killmail_times(start, end, kills=True):
    qs = EveCharacterKillmail.objects.filter(
        killmail_time__gte=start, killmail_time__lt=end
    )
    qs = qs.filter(_kills_q()) if kills else qs.exclude(_kills_q())
    seen: dict[int, datetime] = {}
    for killmail_id, when in qs.values_list("killmail_id", "killmail_time"):
        seen.setdefault(killmail_id, when)
    return seen


def _voice_peak(start, end):
    row = (
        DiscordChannelActivityRecord.objects.filter(
            activity_type=DiscordChannelActivityRecord.VOICE_MINUTE,
            created_on__gte=start,
            created_on__lt=end,
        )
        .annotate(minute=TruncMinute("created_on"))
        .values("minute")
        .annotate(pilots=Count("username", distinct=True))
        .order_by("-pilots", "minute")
        .first()
    )
    if not row:
        return 0, None
    return row["pilots"], row["minute"]


def _freight(start, end):
    agg = EveCorporationContract.objects.filter(
        type="courier",
        status="finished",
        date_completed__gte=start,
        date_completed__lt=end,
    ).aggregate(count=Count("contract_id"), volume=Sum("volume"))
    return agg["count"] or 0, float(agg["volume"] or 0)


def _industry_jobs(start, end) -> int:
    return EveCharacterIndustryJob.objects.filter(
        end_date__gte=start, end_date__lt=end
    ).count()


def _sites(start, end):
    rows = CampaignSiteCompletion.objects.filter(
        occurred_at__gte=start, occurred_at__lt=end
    )
    total = rows.count()
    complexes = rows.filter(site_kind="complex").count()
    return total, complexes


def _day_totals(start, end) -> dict:
    sites, complexes = _sites(start, end)
    freight_count, freight_volume = _freight(start, end)
    return {
        "ships_destroyed": len(_distinct_killmail_times(start, end)),
        "ships_lost": len(_distinct_killmail_times(start, end, kills=False)),
        "warzone_sites": sites,
        "complexes": complexes,
        "industry_jobs": _industry_jobs(start, end),
        "freight_contracts": freight_count,
        "freight_volume": round(freight_volume),
    }


def _week_totals(start, end) -> dict:
    sites, complexes = _sites(start, end)
    freight_count, freight_volume = _freight(start, end)
    peak, peak_at = _voice_peak(start, end)
    return {
        "ships_destroyed": len(_distinct_killmail_times(start, end)),
        "warzone_sites": sites,
        "complexes": complexes,
        "fleets": EveFleet.objects.filter(
            start_time__gte=start, start_time__lt=end
        ).count(),
        "peak_comms": peak,
        "peak_comms_at": peak_at,
        "freight_contracts": freight_count,
        "freight_volume": round(freight_volume),
        "industry_jobs": _industry_jobs(start, end),
    }


def _hourly_kills(end) -> list[dict]:
    """24 hourly buckets of kills, oldest first, ending at ``end``."""
    top = end.replace(minute=0, second=0, microsecond=0)
    start = top - timedelta(hours=23)
    buckets = [
        {"hour": (start + timedelta(hours=i)).hour, "kills": 0}
        for i in range(24)
    ]
    for when in _distinct_killmail_times(start, end).values():
        index = int((when - start).total_seconds() // 3600)
        if 0 <= index < 24:
            buckets[index]["kills"] += 1
    return buckets


def _timezone_kills(end) -> list[dict]:
    """Average kills per EVE hour of day over the last 30 days."""
    start = end - timedelta(days=30)
    per_hour = Counter(
        when.hour for when in _distinct_killmail_times(start, end).values()
    )
    return [
        {"hour": hour, "average_kills": round(per_hour.get(hour, 0) / 30, 1)}
        for hour in range(24)
    ]


# --------------------------------------------------------------------------
# Month moments
# --------------------------------------------------------------------------


def _moments(end) -> list[dict]:
    start = end - timedelta(days=30)
    moments: list[dict] = []

    per_day = Counter(
        when.date() for when in _distinct_killmail_times(start, end).values()
    )
    if per_day:
        day, kills = per_day.most_common(1)[0]
        moments.append(
            {
                "kind": "record",
                "occurred_at": datetime.combine(
                    day, datetime.min.time(), tzinfo=end.tzinfo
                ),
                "title": "Biggest day of the month",
                "value": kills,
                "unit": "ships destroyed",
            }
        )

    peak, peak_at = _voice_peak(start, end)
    if peak and peak_at:
        moments.append(
            {
                "kind": "comms",
                "occurred_at": peak_at,
                "title": "Busiest night on comms this month",
                "value": peak,
                "unit": "pilots at once",
            }
        )

    site_days = Counter(
        CampaignSiteCompletion.objects.filter(
            occurred_at__gte=start, occurred_at__lt=end
        ).values_list("occurred_at", flat=True)
    )
    if site_days:
        by_day = Counter()
        for when, count in site_days.items():
            by_day[when.date()] += count
        day, count = by_day.most_common(1)[0]
        moments.append(
            {
                "kind": "warzone",
                "occurred_at": datetime.combine(
                    day, datetime.min.time(), tzinfo=end.tzinfo
                ),
                "title": "Busiest day in the warzone",
                "value": count,
                "unit": "warzone sites run",
            }
        )

    longest_seconds, longest_end = 0.0, None
    for instance in EveFleetInstance.objects.filter(
        end_time__gte=start, end_time__lt=end, start_time__isnull=False
    ).only("start_time", "end_time"):
        length = (instance.end_time - instance.start_time).total_seconds()
        if length > longest_seconds:
            longest_seconds, longest_end = length, instance.end_time
    if longest_end and longest_seconds >= 3600:
        words = _duration_words(longest_seconds)
        moments.append(
            {
                "kind": "fleet",
                "occurred_at": longest_end,
                "title": f"Longest fleet of the month: {words}",
                "value": round(longest_seconds / 3600, 1),
                "unit": "hours undocked",
            }
        )

    moments.sort(key=lambda m: m["occurred_at"], reverse=True)
    return moments


# --------------------------------------------------------------------------
# Pilot events
# --------------------------------------------------------------------------


def _is_loss(row) -> bool:
    return row["victim_alliance_id"] == MINMATAR_FLEET_ALLIANCE_ID


def _killmail_groups(start, end) -> dict[int, list[dict]]:
    by_killmail: dict[int, list[dict]] = defaultdict(list)
    for row in EveCharacterKillmail.objects.filter(
        killmail_time__gte=start, killmail_time__lt=end
    ).values(
        "id",
        "killmail_id",
        "killmail_time",
        "solar_system_id",
        "victim_character_id",
        "victim_corporation_id",
        "victim_alliance_id",
        "victim_faction_id",
        "character__character_id",
    ):
        by_killmail[row["killmail_id"]].append(row)
    return by_killmail


def _attacker_sides(killmail_row_ids):
    """Per loss: who killed us, counted by alliance (or corporation) and
    by faction, so the line can name the biggest side."""
    sides: dict[int, Counter] = defaultdict(Counter)
    factions: dict[int, Counter] = defaultdict(Counter)
    for (
        row_id,
        alliance_id,
        corporation_id,
        faction_id,
    ) in EveCharacterKillmailAttacker.objects.filter(
        killmail_id__in=killmail_row_ids
    ).values_list(
        "killmail_id", "alliance_id", "corporation_id", "faction_id"
    ):
        if alliance_id == MINMATAR_FLEET_ALLIANCE_ID:
            continue
        if alliance_id or corporation_id:
            sides[row_id][alliance_id or corporation_id] += 1
        if faction_id:
            factions[row_id][faction_id] += 1
    return sides, factions


def _biggest(counter: Counter | None):
    if not counter:
        return None
    return counter.most_common(1)[0][0]


def _victim_entity(first, names) -> str:
    return (
        names.get(first["victim_alliance_id"] or 0)
        or names.get(first["victim_corporation_id"] or 0)
        or FACTION_MILITIA_NAMES.get(first["victim_faction_id"], "")
    )


def _combat_events(start, end) -> list[Event]:
    by_killmail = _killmail_groups(start, end)
    if not by_killmail:
        return []
    firsts = [group[0] for group in by_killmail.values()]
    sides, factions = _attacker_sides(
        [first["id"] for first in firsts if _is_loss(first)]
    )
    entity_ids = {
        first["victim_alliance_id"] or first["victim_corporation_id"]
        for first in firsts
        if not _is_loss(first)
    } | {_biggest(counter) for counter in sides.values()}
    names = _entity_names(entity_ids, entity_ids)
    regions = _region_names_for_systems(f["solar_system_id"] for f in firsts)

    events: list[Event] = []
    for group in by_killmail.values():
        first = group[0]
        ours = sorted({r["character__character_id"] for r in group})
        region = regions.get(first["solar_system_id"], "")
        if _is_loss(first):
            entity = names.get(
                _biggest(sides.get(first["id"])), ""
            ) or FACTION_MILITIA_NAMES.get(
                _biggest(factions.get(first["id"])), ""
            )
            action = (
                f"fought {entity} and went down swinging"
                if entity
                else "went down swinging"
            )
            pilot = first["victim_character_id"] or ours[0]
            events.append(
                Event(first["killmail_time"], "loss", pilot, action, 0, region)
            )
            continue
        entity = _victim_entity(first, names)
        action = f"fought {entity} and won" if entity else "won a fight"
        events.append(
            Event(
                first["killmail_time"],
                "kill",
                ours[0],
                action,
                len(ours) - 1,
                region,
            )
        )
    return events


def _site_events(start, end) -> list[Event]:
    rows = CampaignSiteCompletion.objects.filter(
        occurred_at__gte=start, occurred_at__lt=end, character_id__isnull=False
    ).values_list(
        "occurred_at",
        "character_id",
        "site_kind",
        "campaign_system__eve_solar_system_id",
    )
    rows = list(rows)
    regions = _region_names_for_systems(r[3] for r in rows)
    return [
        Event(
            when,
            "site",
            character_id,
            SITE_ACTIONS.get(kind, DEFAULT_SITE_ACTION),
            0,
            regions.get(system_id, ""),
        )
        for when, character_id, kind, system_id in rows
    ]


def _industry_events(start, end) -> list[Event]:
    rows = list(
        EveCharacterIndustryJob.objects.filter(
            end_date__gte=start,
            end_date__lt=end,
            activity_id=MANUFACTURING_ACTIVITY_ID,
        ).values_list(
            "end_date", "character__character_id", "runs", "blueprint_type_id"
        )
    )
    types = _type_names(r[3] for r in rows)
    # A pilot's parallel jobs of one product finish together: one line.
    batches: dict[tuple, list] = {}
    for when, character_id, runs, blueprint_type_id in rows:
        product = types.get(blueprint_type_id, "").removesuffix(" Blueprint")
        if not product:
            continue
        key = (character_id, product, when.replace(second=0, microsecond=0))
        batch = batches.setdefault(key, [when, 0])
        batch[0] = max(batch[0], when)
        batch[1] += runs or 0
    return [
        Event(
            when,
            "industry",
            character_id,
            f"finished building {runs:,} {product}",
        )
        for (character_id, product, _), (when, runs) in batches.items()
    ]


def _freight_events(start, end) -> list[Event]:
    rows = EveCorporationContract.objects.filter(
        type="courier",
        status="finished",
        date_completed__gte=start,
        date_completed__lt=end,
        acceptor_id__isnull=False,
    ).values_list("date_completed", "acceptor_id", "volume")
    return [
        Event(
            when,
            "freight",
            acceptor_id,
            f"delivered {round(volume or 0):,} m³ of freight",
        )
        for when, acceptor_id, volume in rows
    ]


def _fleet_events(start, end) -> list[Event]:
    events = []
    for instance in EveFleetInstance.objects.filter(
        end_time__gte=start, end_time__lt=end, start_time__isnull=False
    ).only("id", "start_time", "end_time", "boss_id"):
        if not instance.boss_id:
            continue
        pilots = (
            EveFleetInstanceMember.objects.filter(eve_fleet_instance=instance)
            .values("character_id")
            .distinct()
            .count()
        )
        length = (instance.end_time - instance.start_time).total_seconds()
        events.append(
            Event(
                instance.end_time,
                "fleet",
                instance.boss_id,
                f"ran a fleet that lasted {_duration_words(length)}",
                max(pilots - 1, 0),
            )
        )
    return events


def _voice_events(start, end) -> list[Event]:
    """One line per hour: the busiest minute, if enough pilots were on."""
    rows = (
        DiscordChannelActivityRecord.objects.filter(
            activity_type=DiscordChannelActivityRecord.VOICE_MINUTE,
            created_on__gte=start,
            created_on__lt=end,
        )
        .annotate(minute=TruncMinute("created_on"))
        .values_list("minute", "username")
    )
    by_minute: dict[datetime, set[str]] = defaultdict(set)
    for minute, username in rows:
        by_minute[minute].add(username)

    best_per_hour: dict[datetime, tuple[datetime, set[str]]] = {}
    for minute, users in by_minute.items():
        hour = minute.replace(minute=0)
        current = best_per_hour.get(hour)
        if current is None or len(users) > len(current[1]):
            best_per_hour[hour] = (minute, users)

    tags = {u for _, users in best_per_hour.values() for u in users}
    user_ids = dict(
        DiscordUser.objects.filter(discord_tag__in=tags).values_list(
            "discord_tag", "user_id"
        )
    )
    mains = primary_characters_for_users(user_ids.values())
    events = []
    for minute, users in best_per_hour.values():
        if len(users) < VOICE_MIN_PILOTS:
            continue
        character_id = None
        for tag in sorted(users):
            primary = mains.get(user_ids.get(tag))
            if primary:
                character_id = primary.character_id
                break
        if character_id is None:
            continue
        events.append(
            Event(
                minute,
                "comms",
                character_id,
                "were hanging out on comms",
                len(users) - 1,
            )
        )
    return events


def _events(start, end) -> list[dict]:
    events: list[Event] = []
    for source in (
        _combat_events,
        _site_events,
        _industry_events,
        _freight_events,
        _fleet_events,
        _voice_events,
    ):
        events.extend(source(start, end))
    events = [e for e in events if e.character_id]
    events.sort(key=lambda e: e.occurred_at, reverse=True)
    events = events[:MAX_EVENTS]
    names = _character_names(e.character_id for e in events)
    return [
        {
            "occurred_at": e.occurred_at,
            "kind": e.kind,
            "character_id": e.character_id,
            "character_name": names.get(
                e.character_id, "A Minmatar Fleet pilot"
            ),
            "others": e.others,
            "action": e.action,
            "region": e.region,
        }
        for e in events
    ]


# --------------------------------------------------------------------------
# Public entry points
# --------------------------------------------------------------------------


def build_fast(now=None) -> dict:
    now = now or timezone.now()
    end = now - DELAY
    return {
        "generated_at": now,
        "delay_minutes": int(DELAY.total_seconds() // 60),
        "day": _day_totals(end - timedelta(hours=24), end),
        "hourly_kills": _hourly_kills(end),
        "week": _week_totals(end - timedelta(days=7), end),
        "events": _events(end - timedelta(hours=24), end),
    }


def build_slow(now=None) -> dict:
    now = now or timezone.now()
    end = now - DELAY
    return {
        "timezone_kills": _timezone_kills(end),
        "moments": _moments(end),
    }


def landing_pulse() -> dict:
    fast = FAST.get_or_compute(build_fast)
    slow = SLOW.get_or_compute(build_slow)
    return {**fast, **slow}
