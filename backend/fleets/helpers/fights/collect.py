"""Gather a fleet's killmails and events for the fight timeline.

Killmails are matched to the fleet exactly as on the fleet kills card
(feed.helpers.fleet_kills): a loss when the victim was in fleet at that
moment, a kill when any in-fleet pilot was on it. On top of that each row
records who was on each side, which the round report needs.

Events come from the fleet poller's rows: when tracking started and ended,
waves of pilots joining, and reship waves from the ship snapshots.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta

from eveonline.killmail_classes import CAPSULE_TYPE_IDS
from eveuniverse.models import EveSolarSystem
from feed.helpers.eve_names import resolve_entity_names, resolve_type_names
from feed.helpers.fleet_kills import (
    OUTCOME_LOSS,
    iter_instance_killmails,
    killmail_isk,
    member_windows,
    stored_killmail_rows,
)
from feed.models import FeedEventFleetLink, FeedKillmail
from fleets.helpers.presence import was_present

logger = logging.getLogger(__name__)

# Events: pilots or ship changes less than this far apart form one wave.
WAVE_CHAIN_GAP = timedelta(minutes=3)
JOIN_WAVE_MIN = 10
# Joins in the first minutes are the form-up, not reinforcements.
FORM_UP = timedelta(minutes=15)
RESHIP_WAVE_MIN = 8
RESHIP_WAVE_SHARE = 0.25
OUR_GROUPS_KEPT = 10


def _group(entity: dict) -> int | None:
    return entity.get("alliance_id") or entity.get("corporation_id") or None


def _instances(fleet):
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetInstance

    return list(
        EveFleetInstance.objects.filter(eve_fleet=fleet).order_by("start_time")
    )


def _card_rows(instance) -> dict[int, dict]:
    """The settled fleet kills card's rows, for mails the feed purged."""
    link = (
        FeedEventFleetLink.objects.filter(
            fleet_instance_id=instance.id,
            feed_event__rollup_code="fleet_kills",
        )
        .select_related("feed_event")
        .first()
    )
    return stored_killmail_rows(link.feed_event if link else None)


def _row_from_card(card: dict) -> dict:
    return {
        "id": card["killmail_id"],
        "t": card["killmail_time"],
        "outcome": card["outcome"],
        "system": card["solar_system_id"],
        "ship": card.get("victim_ship_type_id"),
        "victim": card.get("victim_character_id"),
        "victim_group": None,
        "isk": card.get("isk_value") or 0,
        "pending": False,
        "pod": bool(card.get("is_capsule")),
        "pilots": [],
        "hostiles": [],
    }


def collect_rows(fleet) -> tuple[list[dict], Counter, list]:
    """Every matched killmail across the fleet's instances, oldest first.

    Returns ``(rows, our_groups, instances)``; ``our_groups`` counts the
    alliance (or corporation) of our pilots on the mails.
    """
    instances = _instances(fleet)
    rows: dict[int, dict] = {}
    raw_needed: list[int] = []
    our_groups: Counter = Counter()
    for instance in instances:
        windows = member_windows(instance)
        for item in iter_instance_killmails(instance, windows):
            killmail = item.killmail
            if killmail.killmail_id in rows:
                continue
            hostiles = []
            for attacker in killmail.attacker_summary or []:
                character = attacker.get("character_id")
                if not character:
                    continue
                if character in item.pilots:
                    our_groups[_group(attacker)] += 1
                elif item.outcome == OUTCOME_LOSS:
                    hostiles.append([_group(attacker), character])
            rows[killmail.killmail_id] = {
                "id": killmail.killmail_id,
                "t": killmail.killmail_time.isoformat(),
                "outcome": item.outcome,
                "system": killmail.solar_system_id,
                "ship": killmail.victim_ship_type_id,
                "victim": killmail.victim_character_id,
                "victim_group": None,
                "isk": killmail_isk(killmail),
                "pending": "totalValue" not in (killmail.zkb_meta or {}),
                "pod": killmail.victim_ship_type_id in CAPSULE_TYPE_IDS,
                "pilots": sorted(item.pilots),
                "hostiles": hostiles,
            }
            raw_needed.append(killmail.killmail_id)
        # Mails the feed has purged survive on the settled kills card.
        if instance.end_time is not None:
            for killmail_id, card in _card_rows(instance).items():
                rows.setdefault(killmail_id, _row_from_card(card))

    victims = FeedKillmail.objects.filter(
        killmail_id__in=raw_needed
    ).values_list("killmail_id", "raw_killmail")
    for killmail_id, raw in victims:
        victim = (raw or {}).get("victim") or {}
        row = rows[killmail_id]
        row["victim_group"] = _group(victim)
        if row["outcome"] == OUTCOME_LOSS:
            our_groups[_group(victim)] += 1
    our_groups.pop(None, None)
    ordered = sorted(rows.values(), key=lambda r: (r["t"], r["id"]))
    return ordered, our_groups, instances


def _named(names: dict[int, str], prior: dict) -> dict[str, str]:
    """ESI names, minus the placeholders it fills in when a lookup fails."""
    kept = {str(key): value for key, value in (prior or {}).items()}
    for entity_id, name in names.items():
        if name and not name.endswith(f" {entity_id}"):
            kept[str(entity_id)] = name
    return kept


def lookup_entity_names(ids: set[int]) -> dict[int, str]:
    """ESI names for characters, corporations and alliances, or none."""
    if not ids:
        return {}
    try:
        return resolve_entity_names(ids)
    except Exception:  # pylint: disable=broad-exception-caught
        # Names are cosmetic; an ESI outage must not stop the rebuild.
        logger.warning("Could not resolve fight timeline names")
        return {}


def resolve_names(
    rows: list[dict], our_groups: Counter, prior: dict | None
) -> dict:
    """Names for systems, ships, groups and victims, reusing stored ones."""
    prior = prior or {}
    systems = {r["system"] for r in rows}
    ships = {r["ship"] for r in rows if r["ship"]}
    groups = {r["victim_group"] for r in rows if r["victim_group"]}
    groups |= {g for r in rows for g, _ in r["hostiles"] if g}
    characters = {r["victim"] for r in rows if r["victim"]}

    system_names = {
        str(system_id): name
        for system_id, name in EveSolarSystem.objects.filter(
            id__in=systems
        ).values_list("id", "name")
    }
    ship_names = {
        str(type_id): name
        for type_id, name in resolve_type_names(ships).items()
    }

    known_groups = prior.get("groups") or {}
    known_characters = prior.get("characters") or {}
    unknown = {g for g in groups if str(g) not in known_groups}
    unknown |= {c for c in characters if str(c) not in known_characters}
    resolved = lookup_entity_names(unknown)
    return {
        "systems": {**(prior.get("systems") or {}), **system_names},
        "ships": {**(prior.get("ships") or {}), **ship_names},
        "groups": _named(
            {g: resolved[g] for g in groups if g in resolved}, known_groups
        ),
        "characters": _named(
            {c: resolved[c] for c in characters if c in resolved},
            known_characters,
        ),
        "our_groups": [g for g, _ in our_groups.most_common(OUR_GROUPS_KEPT)],
    }


def _waves(times: list[datetime]) -> list[list[datetime]]:
    waves: list[list[datetime]] = []
    for moment in sorted(times):
        if waves and moment - waves[-1][-1] <= WAVE_CHAIN_GAP:
            waves[-1].append(moment)
        else:
            waves.append([moment])
    return waves


def collect_events(instances: list) -> list[dict]:
    """Tracking start and end, join waves and reship waves, oldest first."""
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetInstanceMemberShipSnapshot

    if not instances:
        return []
    start = min(i.start_time for i in instances)
    ended = all(i.end_time for i in instances)
    end = max(i.end_time for i in instances) if ended else None
    events: list[dict] = [
        {"kind": "start", "at": start.isoformat(), "count": 0, "ships": []}
    ]

    windows: dict[int, tuple[datetime, datetime]] = {}
    for instance in instances:
        for character, window in member_windows(instance).items():
            prior = windows.get(character)
            windows[character] = (
                (min(prior[0], window[0]), max(prior[1], window[1]))
                if prior
                else window
            )

    joins = [first for first, _ in windows.values() if first > start + FORM_UP]
    for wave in _waves(joins):
        if len(wave) >= JOIN_WAVE_MIN:
            events.append(
                {
                    "kind": "joined",
                    "at": wave[0].isoformat(),
                    "count": len(wave),
                    "ships": [],
                }
            )

    changes: list[tuple[datetime, str]] = []
    seen: set[int] = set()
    for member_id, type_id, name, moment in (
        EveFleetInstanceMemberShipSnapshot.objects.filter(
            member__eve_fleet_instance__in=instances
        )
        .order_by("member_id", "created_at")
        .values_list("member_id", "ship_type_id", "ship_name", "created_at")
    ):
        # A member's first snapshot is the ship they joined in.
        if member_id not in seen:
            seen.add(member_id)
            continue
        if type_id in CAPSULE_TYPE_IDS:
            continue
        changes.append((moment, name))
    by_time: dict[datetime, list[str]] = {}
    for moment, name in changes:
        by_time.setdefault(moment, []).append(name)
    for wave in _waves([moment for moment, _ in changes]):
        present = sum(
            1 for window in windows.values() if was_present(window, wave[0])
        )
        if len(wave) < max(RESHIP_WAVE_MIN, RESHIP_WAVE_SHARE * present):
            continue
        ships = Counter(
            name for moment in sorted(set(wave)) for name in by_time[moment]
        )
        events.append(
            {
                "kind": "reship",
                "at": wave[len(wave) // 2].isoformat(),
                "count": len(wave),
                "ships": [
                    {"name": n, "count": c} for n, c in ships.most_common(2)
                ],
            }
        )

    if end is not None:
        events.append(
            {"kind": "end", "at": end.isoformat(), "count": 0, "ships": []}
        )
    return sorted(events, key=lambda e: e["at"])


def tracking_bounds(instances: list) -> tuple[datetime, datetime | None]:
    start = min(i.start_time for i in instances)
    if all(i.end_time for i in instances):
        return start, max(i.end_time for i in instances)
    return start, None
