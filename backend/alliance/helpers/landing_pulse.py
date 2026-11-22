"""
Public "heartbeat" for the new landing page (/landing-new).

Killmails are live: they are public on zKillboard the moment they happen.
Fleets and voice comms run 60 minutes behind, so the page never says that
the alliance is forming or on comms right now. Kills name a region, never a
system; comms lines never name a channel; fleets appear only after they end.

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
from discord.models import DiscordChannelActivityRecord
from eveonline.client import live_esi_allowed
from eveonline.constants import (
    AMARR_FACTION_ID,
    CALDARI_FACTION_ID,
    GALLENTE_FACTION_ID,
    MINMATAR_FACTION_ID,
    MINMATAR_FLEET_ALLIANCE_ID,
)
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCharacterIndustryJob,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
    EveCharacterMiningDelta,
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
# A kill or loss reads as a fleet fight ("fought X and won") only when a fleet
# this big was involved; smaller gangs and solo read "killed a Rifter".
LARGE_FLEET_PILOTS = 10

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
    "advantage_site": "ran an advantage site",
}
DEFAULT_SITE_ACTION = "ran a warzone site"


@dataclass
class Event:
    """One feed line: "<pilot> <verb> <subject> <tail>". The subject (a ship,
    an ore or the side we fought) gets an icon from the EVE image server, so
    it is kept apart from the words around it."""

    occurred_at: datetime
    kind: str
    character_id: int | None
    verb: str
    subject: str = ""
    subject_type: str = ""
    subject_id: int = 0
    tail: str = ""
    others: int = 0
    region: str = ""
    # A large-fleet line ("fought X and won"); the hero's Live band leaves
    # these to the week table's Fleet activity tab.
    group: bool = False
    # m³ for a mining line, so the page can add it to the day's total.
    amount: int = 0

    @property
    def action(self) -> str:
        return " ".join(p for p in (self.verb, self.subject, self.tail) if p)


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


def _mined_volume(start, end) -> float:
    """m³ of ore the ledger syncs saw mined in the window."""
    return sum(
        (volume or 0) * quantity
        for volume, quantity in EveCharacterMiningDelta.objects.filter(
            observed_at__gte=start, observed_at__lt=end
        ).values_list("eve_type__volume", "quantity")
    )


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
        "mined_volume": round(_mined_volume(start, end)),
    }


def _week_totals(start, end) -> dict:
    sites, complexes = _sites(start, end)
    freight_count, freight_volume = _freight(start, end)
    # Fleets and comms are held back an hour; everything else is live.
    peak, peak_at = _voice_peak(start - DELAY, end - DELAY)
    return {
        "ships_destroyed": len(_distinct_killmail_times(start, end)),
        "warzone_sites": sites,
        "complexes": complexes,
        "fleets": EveFleet.objects.filter(
            start_time__gte=start - DELAY, start_time__lt=end - DELAY
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

    peak, peak_at = _voice_peak(start - DELAY, end - DELAY)
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
        end_time__gte=start - DELAY,
        end_time__lt=end - DELAY,
        start_time__isnull=False,
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
        "ship_type_id",
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
        if alliance_id:
            sides[row_id][("alliance", alliance_id)] += 1
        elif corporation_id:
            sides[row_id][("corporation", corporation_id)] += 1
        if faction_id:
            factions[row_id][faction_id] += 1
    return sides, factions


def _large_fleet_windows(start, end) -> dict[int, list[tuple]]:
    """Character -> (start, end) of each fleet of LARGE_FLEET_PILOTS or more
    they were in that overlaps the window. A fleet still running ends now."""
    instances = {
        row["id"]: row
        for row in EveFleetInstance.objects.filter(
            Q(end_time__isnull=True) | Q(end_time__gte=start),
            start_time__isnull=False,
            start_time__lt=end,
        )
        .annotate(
            pilots=Count("evefleetinstancemember__character_id", distinct=True)
        )
        .filter(pilots__gte=LARGE_FLEET_PILOTS)
        .values("id", "start_time", "end_time")
    }
    windows: dict[int, list[tuple]] = defaultdict(list)
    for instance_id, character_id in EveFleetInstanceMember.objects.filter(
        eve_fleet_instance_id__in=instances.keys()
    ).values_list("eve_fleet_instance_id", "character_id"):
        row = instances[instance_id]
        windows[character_id].append(
            (row["start_time"], row["end_time"] or end)
        )
    return windows


def _in_large_fleet(character_ids, when, windows) -> bool:
    return any(
        start <= when <= finish
        for character_id in character_ids
        for start, finish in windows.get(character_id, ())
    )


def _article(name: str) -> str:
    return "an" if name[:1].lower() in "aeiou" else "a"


def _biggest(counter: Counter | None):
    if not counter:
        return None
    return counter.most_common(1)[0][0]


def _victim_entity(first) -> tuple[str, int]:
    if first["victim_alliance_id"]:
        return "alliance", first["victim_alliance_id"]
    if first["victim_corporation_id"]:
        return "corporation", first["victim_corporation_id"]
    return "", 0


def _entity_subject(key, names, faction_id) -> tuple[str, str, int]:
    """The side we fought as (name, subject_type, subject_id); a militia when
    no alliance or corporation name is known."""
    if key and names.get(key[1]):
        return names[key[1]], key[0], key[1]
    militia = FACTION_MILITIA_NAMES.get(faction_id)
    if militia:
        return militia, "faction", faction_id
    return "", "", 0


def _combat_events(start, end) -> list[Event]:
    by_killmail = _killmail_groups(start, end)
    if not by_killmail:
        return []
    firsts = [group[0] for group in by_killmail.values()]
    sides, factions = _attacker_sides(
        [first["id"] for first in firsts if _is_loss(first)]
    )
    keys = {
        _victim_entity(first) for first in firsts if not _is_loss(first)
    } | {_biggest(counter) for counter in sides.values()}
    keys = {k for k in keys if k and k[1]}
    names = _entity_names(
        (k[1] for k in keys if k[0] == "alliance"),
        (k[1] for k in keys if k[0] == "corporation"),
    )
    regions = _region_names_for_systems(f["solar_system_id"] for f in firsts)
    ships = _type_names(f["ship_type_id"] for f in firsts)
    fleets = _large_fleet_windows(start, end)

    events: list[Event] = []
    for group in by_killmail.values():
        first = group[0]
        ours = sorted({r["character__character_id"] for r in group})
        region = regions.get(first["solar_system_id"], "")
        loss = _is_loss(first)
        pilots = [first["victim_character_id"]] if loss else ours
        pilot = (first["victim_character_id"] or ours[0]) if loss else ours[0]
        large = len(ours) >= LARGE_FLEET_PILOTS or _in_large_fleet(
            pilots, first["killmail_time"], fleets
        )
        if not large:
            # Small gang or solo: just the hull.
            ship = ships.get(first["ship_type_id"], "") or "ship"
            verb = "lost" if loss else "killed"
            events.append(
                Event(
                    first["killmail_time"],
                    "loss" if loss else "kill",
                    pilot,
                    f"{verb} {_article(ship)}",
                    ship,
                    "type",
                    first["ship_type_id"],
                    others=0 if loss else len(ours) - 1,
                    region=region,
                )
            )
            continue
        if loss:
            subject, subject_type, subject_id = _entity_subject(
                _biggest(sides.get(first["id"])),
                names,
                _biggest(factions.get(first["id"])),
            )
            tail = "and went down swinging"
        else:
            subject, subject_type, subject_id = _entity_subject(
                _victim_entity(first), names, first["victim_faction_id"]
            )
            tail = "and won"
        if subject:
            verb = "fought"
        else:
            verb, tail = ("went down swinging" if loss else "won a fight"), ""
        events.append(
            Event(
                first["killmail_time"],
                "loss" if loss else "kill",
                pilot,
                verb,
                subject,
                subject_type,
                subject_id,
                tail,
                others=0 if loss else len(ours) - 1,
                region=region,
                group=True,
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
            region=regions.get(system_id, ""),
        )
        for when, character_id, kind, system_id in rows
    ]


def _mining_events(start, end) -> list[Event]:
    """What each ledger sync saw a pilot mine, one line per pilot and ore."""
    rows = list(
        EveCharacterMiningDelta.objects.filter(
            observed_at__gte=start, observed_at__lt=end
        ).values_list(
            "observed_at",
            "character__character_id",
            "eve_type_id",
            "eve_type__name",
            "eve_type__volume",
            "quantity",
            "solar_system_id",
        )
    )
    regions = _region_names_for_systems(r[6] for r in rows)
    batches: dict[tuple, list] = {}
    for when, character_id, type_id, ore, volume, quantity, sid in rows:
        key = (character_id, type_id, when.replace(second=0, microsecond=0))
        batch = batches.setdefault(key, [when, ore, 0.0, sid])
        batch[2] += (volume or 0) * quantity
    return [
        Event(
            when,
            "mining",
            character_id,
            f"mined {round(m3):,} m³ of",
            ore,
            "type",
            type_id,
            region=regions.get(sid, ""),
            amount=round(m3),
        )
        for (character_id, type_id, _), (when, ore, m3, sid) in batches.items()
        if m3 >= 1
    ]


def event_rows(events: list[Event]) -> list[dict]:
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
            "verb": e.verb,
            "subject": e.subject,
            "subject_type": e.subject_type,
            "subject_id": e.subject_id,
            "tail": e.tail,
            "region": e.region,
            "amount": e.amount,
        }
        for e in events
    ]


def _events(start, end) -> list[dict]:
    """The hero's Live band: one pilot's own kill, loss, site or mining run.
    Large-fleet fights are left to the week table's Fleet activity tab."""
    events = [e for e in _combat_events(start, end) if not e.group]
    events += _site_events(start, end) + _mining_events(start, end)
    events = [e for e in events if e.character_id]
    events.sort(key=lambda e: e.occurred_at, reverse=True)
    return event_rows(events[:MAX_EVENTS])


# --------------------------------------------------------------------------
# Public entry points
# --------------------------------------------------------------------------


def build_fast(now=None) -> dict:
    now = now or timezone.now()
    return {
        "generated_at": now,
        "delay_minutes": int(DELAY.total_seconds() // 60),
        "day": _day_totals(now - timedelta(hours=24), now),
        "hourly_kills": _hourly_kills(now),
        "week": _week_totals(now - timedelta(days=7), now),
        "events": _events(now - timedelta(hours=24), now),
    }


def build_slow(now=None) -> dict:
    now = now or timezone.now()
    end = now
    return {
        "timezone_kills": _timezone_kills(end),
        "moments": _moments(end),
    }


def landing_pulse() -> dict:
    fast = FAST.get_or_compute(build_fast)
    slow = SLOW.get_or_compute(build_slow)
    return {**fast, **slow}
