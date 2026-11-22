"""Metenox Moon Drills killed at our moons, from zKillboard.

zKillboard lists Metenox losses newest first with the moon each died at
(`zkb.locationID`). The killmail from ESI gives the system, the owner and
the attackers. A kill is kept only when it died at a moon we track; the
newest one says who last held that moon.
"""

from __future__ import annotations

import logging
import re
import time
from collections import Counter
from datetime import datetime

import requests
from django.core.cache import cache
from django.db import IntegrityError

from eveonline.client import EsiClient
from feed.helpers.eve_names import resolve_entity_names
from feed.helpers.zkill_client import (
    ZKILL_API_BASE,
    fetch_esi_killmail,
    zkill_get,
)
from moons.models import EveMoon, MetenoxKill

logger = logging.getLogger(__name__)

METENOX_TYPE_ID = 81826
LOSSES_URL = ZKILL_API_BASE + "/losses/shipTypeID/%d/page/{page}/" % (
    METENOX_TYPE_ID
)
# The newest killmail id already looked at, so a run stops where the last
# one did. Without it (first run, cleared cache) a run walks BACKFILL_PAGES.
CURSOR_KEY = "moons:metenox:last_killmail_id"
BACKFILL_PAGES = 5
ROUTINE_PAGES = 2
# EVE moon ids sit in this range; other location ids are not moons.
MOON_ID_RANGE = range(40_000_000, 50_000_000)
MOON_NAME = re.compile(
    r"^(?P<system>.+) (?P<planet>[IVXLC]+) - Moon (?P<moon>\d+)$"
)


def parse_moon_name(name: str) -> tuple[str, str, int] | None:
    """("Gomati", "VII", 2) for "Gomati VII - Moon 2"."""
    match = MOON_NAME.match(name or "")
    if not match:
        return None
    return match["system"], match["planet"], int(match["moon"])


def _our_moon(location_id: int, system_name: str) -> EveMoon | None:
    """The moon we track at this location, remembering its EVE id."""
    moon = EveMoon.objects.filter(eve_moon_id=location_id).first()
    if moon or location_id not in MOON_ID_RANGE:
        return moon
    if not EveMoon.objects.filter(system=system_name).exists():
        return None
    parsed = parse_moon_name(EsiClient(None).get_moon(location_id).name)
    if not parsed:
        return None
    system, planet, number = parsed
    moon = EveMoon.objects.filter(
        system=system, planet=planet, moon=number
    ).first()
    if moon and moon.eve_moon_id is None:
        moon.eve_moon_id = location_id
        try:
            moon.save(update_fields=["eve_moon_id"])
        except IntegrityError:
            logger.warning("Moon id %s already on another moon", location_id)
    return moon


def _killer(attackers: list[dict]) -> tuple[int | None, int]:
    """The alliance (else corporation) with the most damage, and the
    number of pilots on the mail."""
    damage = Counter()
    pilots = 0
    for attacker in attackers:
        if attacker.get("character_id"):
            pilots += 1
        group = attacker.get("alliance_id") or attacker.get("corporation_id")
        if group:
            damage[group] += attacker.get("damage_done") or 0
    killer = damage.most_common(1)[0][0] if damage else None
    return killer, pilots


def _kill_row(moon: EveMoon, entry: dict, raw: dict) -> MetenoxKill:
    victim = raw.get("victim") or {}
    killer_id, pilots = _killer(raw.get("attackers") or [])
    return MetenoxKill(
        moon=moon,
        killmail_id=entry["killmail_id"],
        killmail_hash=entry["zkb"]["hash"],
        killed_at=datetime.fromisoformat(
            raw["killmail_time"].replace("Z", "+00:00")
        ),
        owner_corporation_id=victim.get("corporation_id"),
        owner_alliance_id=victim.get("alliance_id"),
        killer_id=killer_id,
        attacker_count=pilots,
    )


def _name_rows(rows: list[MetenoxKill]) -> None:
    ids = set()
    for row in rows:
        ids |= {
            row.owner_corporation_id,
            row.owner_alliance_id,
            row.killer_id,
        }
    try:
        names = resolve_entity_names(i for i in ids if i)
    except Exception:  # pylint: disable=broad-exception-caught
        # Names are cosmetic; the next run of the page shows ids' names.
        logger.warning("Could not resolve Metenox kill names")
        names = {}
    for row in rows:
        row.owner_corporation_name = names.get(row.owner_corporation_id, "")
        row.owner_alliance_name = names.get(row.owner_alliance_id, "")
        row.killer_name = names.get(row.killer_id, "")


def _losses_page(page: int) -> list[dict]:
    response = zkill_get(LOSSES_URL.format(page=page))
    if response.status_code != 200:
        logger.warning("zKill Metenox losses: HTTP %s", response.status_code)
        return []
    data = response.json()
    return data if isinstance(data, list) else []


class _Run:
    """One sync: what it has seen, kept and failed to fetch."""

    def __init__(self, cursor: int | None):
        self.cursor = cursor
        self.known = set(
            MetenoxKill.objects.values_list("killmail_id", flat=True)
        )
        self.systems: dict[int, str] = {}
        self.newest = cursor or 0
        self.rows: list[MetenoxKill] = []
        self.looked = 0
        # A kill ESI would not give us is looked at again next run.
        self.failed = False

    def system_name(self, system_id: int) -> str:
        if system_id not in self.systems:
            self.systems[system_id] = (
                EsiClient(None).get_solar_system(system_id).name
            )
        return self.systems[system_id]

    def take(self, entry: dict) -> bool:
        """Look at one zKill entry; False once it is older than the cursor."""
        killmail_id = entry.get("killmail_id")
        zkb = entry.get("zkb") or {}
        if not killmail_id or not zkb.get("hash"):
            return True
        if self.cursor and killmail_id <= self.cursor:
            return False
        self.newest = max(self.newest, killmail_id)
        if killmail_id in self.known:
            return True
        self.looked += 1
        try:
            raw = fetch_esi_killmail(killmail_id, zkb["hash"])
        except (requests.RequestException, ValueError):
            raw = None
        if not raw:
            self.failed = True
            return True
        system = self.system_name(raw.get("solar_system_id"))
        moon = _our_moon(zkb.get("locationID") or 0, system)
        if moon:
            self.rows.append(_kill_row(moon, entry, raw))
        return True


def sync_metenox_kills(sleep_seconds: float = 1.0) -> dict:
    """Store new Metenox kills at our moons. Safe to run twice."""
    cursor = cache.get(CURSOR_KEY)
    run = _Run(cursor)
    for page in range(1, (ROUTINE_PAGES if cursor else BACKFILL_PAGES) + 1):
        if page > 1:
            time.sleep(sleep_seconds)
        try:
            entries = _losses_page(page)
        except (requests.RequestException, ValueError):
            logger.warning("zKill Metenox losses page %s failed", page)
            break
        caught_up = not all(run.take(entry) for entry in entries)
        if caught_up or not entries:
            break

    _name_rows(run.rows)
    MetenoxKill.objects.bulk_create(run.rows, ignore_conflicts=True)
    if run.newest and not run.failed:
        cache.set(CURSOR_KEY, run.newest, timeout=None)
    return {"looked_at": run.looked, "stored": len(run.rows)}
