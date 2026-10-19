"""Give fleets that ended before the history features their history.

The live tick only reaches fleets that ended in the last few hours, so an
older fleet has no kills card and no fight timeline. This builds both. It
first asks zKill for the mails the feed never kept: until the fleet pilot
ingest, the feed only kept mails in the monitored systems. zKill's
``pastSeconds`` stops at a week, so this pages each group by month instead,
newest first, until it is past the fleets it is filling in.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

import requests
from django.utils import timezone

from eveonline.constants import MINMATAR_FLEET_ALLIANCE_ID
from feed.helpers.fleet_kills import instance_bounds, member_windows
from feed.helpers.ingest import upsert_feed_killmail_from_raw
from feed.helpers.zkill_client import ZKILL_API_BASE, zkill_get
from feed.models import FeedEvent, FeedKillmail
from feed.rollups.fleet_kills import (
    EXCLUDED_FLEET_TYPES,
    build_fleet_kills_result,
    fleet_kills_cluster_key,
)
from feed.rollups.writer import write_rollup_results
from fleets.helpers.fights import timeline as fights
from fleets.helpers.fights.rounds import group_kind, parse_time
from fleets.helpers.presence import was_present

logger = logging.getLogger(__name__)

MAX_PAGES = 60
SLEEP_SECONDS = 1.1


@dataclass
class Target:
    """One fleet instance's time span and who was in it when."""

    fleet_id: int
    start: datetime
    end: datetime
    windows: dict[int, tuple[datetime, datetime]]

    def pilots_on(self, raw: dict, moment: datetime) -> frozenset[int]:
        characters = {(raw.get("victim") or {}).get("character_id")}
        characters |= {
            attacker.get("character_id")
            for attacker in raw.get("attackers") or []
        }
        return frozenset(
            character
            for character in characters
            if character in self.windows
            and was_present(self.windows[character], moment)
        )


def backfill_fleets(since: datetime, *, now=None, fleet_ids=None, force=False):
    """Ended fleets tracked since ``since`` that have no settled timeline.

    A live fleet, or one the tick still settles (ended under two hours
    ago), is left to the tick. ``force`` takes settled ones too.
    """
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleet

    now = now or timezone.now()
    fleets = (
        EveFleet.objects.filter(evefleetinstance__start_time__gte=since)
        .exclude(type__in=EXCLUDED_FLEET_TYPES)
        .distinct()
        .order_by("start_time")
    )
    if fleet_ids:
        fleets = fleets.filter(id__in=fleet_ids)
    if not force:
        fleets = fleets.exclude(fight_timeline__settled_at__isnull=False)
    kept = []
    for fleet in fleets:
        end = fights.ended_at(fleet)
        if fights.is_live(fleet, now):
            continue
        if end is not None and end > now - fights.SETTLE_AFTER:
            continue
        kept.append(fleet)
    return kept


def _instances(fleet):
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetInstance

    return EveFleetInstance.objects.filter(eve_fleet=fleet)


def _targets(fleet) -> list[Target]:
    targets = []
    for instance in _instances(fleet):
        windows = member_windows(instance)
        if not windows:
            continue
        start, end = instance_bounds(instance, windows)
        targets.append(Target(fleet.id, start, end, windows))
    return targets


def _months(start: datetime, end: datetime) -> list[tuple[int, int]]:
    months = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def _entry(entry: dict, targets: list[Target]) -> str:
    zkb = entry.get("zkb") or {}
    killmail_id = entry.get("killmail_id")
    if not killmail_id or not entry.get("victim"):
        return "skipped"
    moment = parse_time(entry["killmail_time"].replace("Z", "+00:00"))
    pilots = frozenset().union(
        *(
            target.pilots_on(entry, moment)
            for target in targets
            if target.start <= moment <= target.end
        )
    )
    if not pilots:
        return "outside"
    existing = FeedKillmail.objects.filter(killmail_id=killmail_id).first()
    if existing is not None:
        meta = existing.zkb_meta or {}
        if "totalValue" not in meta and "totalValue" in zkb:
            existing.zkb_meta = {**meta, **zkb}
            existing.save(update_fields=["zkb_meta"])
            return "repriced"
        return "known"
    stored = upsert_feed_killmail_from_raw(
        entry, zkb_meta=zkb, source="backfill", fleet_pilots=pilots
    )
    return "added" if stored else "skipped"


def _plan(fleets) -> tuple[list[Target], dict, dict]:
    """Each fleet's spans, and the zKill months to page for its groups.

    The groups are each fleet's top groups on the mails the feed already
    has, plus the alliance, so a fleet whose fights all happened outside
    the warzone is still found. Returns ``(targets, months, names)`` where
    ``months`` maps ``(group, year, month)`` to the earliest start in it.
    """
    targets: list[Target] = []
    names: dict = {"alliances": [MINMATAR_FLEET_ALLIANCE_ID]}
    months: dict[tuple[int, int, int], datetime] = {}
    for fleet in fleets:
        fleet_targets = _targets(fleet)
        if not fleet_targets:
            continue
        try:
            fleet_names = fights.rebuild(fleet).names or {}
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Fleet history rebuild failed for %s", fleet.id)
            continue
        targets += fleet_targets
        names["alliances"] = sorted(
            set(names["alliances"]) | set(fleet_names.get("alliances") or ())
        )
        groups = list(fleet_names.get("our_groups") or [])
        groups = groups[: fights.SWEEP_GROUPS]
        if MINMATAR_FLEET_ALLIANCE_ID not in groups:
            groups.append(MINMATAR_FLEET_ALLIANCE_ID)
        for target in fleet_targets:
            for year, month in _months(target.start, target.end):
                for group in groups:
                    key = (group, year, month)
                    months[key] = min(
                        months.get(key, target.start), target.start
                    )
    return targets, months, names


def _page_month(path, earliest, targets, stats, *, max_pages, sleep_seconds):
    """Page one group's month, newest first, until it is before ``earliest``."""
    for page in range(1, max_pages + 1):
        url = f"{ZKILL_API_BASE}/{path}/page/{page}/"
        try:
            response = zkill_get(url)
            response.raise_for_status()
            entries = response.json()
        except (requests.RequestException, ValueError):
            logger.warning("zKill backfill failed: %s", url)
            stats["errors"] += 1
            return
        stats["pages"] += 1
        time.sleep(sleep_seconds)
        if not isinstance(entries, list) or not entries:
            return
        for entry in entries:
            stats[_entry(entry, targets)] += 1
        oldest = min(
            (e["killmail_time"] for e in entries if e.get("killmail_time")),
            default=None,
        )
        if oldest and parse_time(oldest.replace("Z", "+00:00")) < earliest:
            return
    logger.warning("zKill backfill stopped at %s pages: %s", max_pages, path)
    stats["truncated"] += 1


def fetch_missed_killmails(
    fleets,
    *,
    max_pages: int = MAX_PAGES,
    sleep_seconds: float = SLEEP_SECONDS,
) -> dict:
    """Page zKill by month for our groups and keep the fleets' missed mails."""
    targets, months, names = _plan(fleets)
    stats: dict = defaultdict(int)
    for (group, year, month), earliest in sorted(months.items()):
        _page_month(
            f"{group_kind(group, names)}ID/{group}/year/{year}/month/{month}",
            earliest,
            targets,
            stats,
            max_pages=max_pages,
            sleep_seconds=sleep_seconds,
        )
    return dict(stats)


def backfill_fleet(fleet, *, now=None, swept=False) -> dict:
    """Write each instance's kills card, then settle the fight timeline."""
    now = now or timezone.now()
    cards = 0
    for instance in _instances(fleet):
        prior = FeedEvent.objects.filter(
            rollup_code="fleet_kills",
            cluster_key=fleet_kills_cluster_key(instance.id),
        ).first()
        result = build_fleet_kills_result(instance, prior)
        if result is not None:
            cards += write_rollup_results([result])
    timeline = fights.settle(fleet, now=now)
    if swept:
        type(timeline).objects.filter(pk=timeline.pk).update(swept_at=now)
    totals = (timeline.payload or {}).get("totals") or {}
    return {
        "cards": cards,
        "rounds": (timeline.payload or {}).get("round_count", 0),
        "killmails": len(timeline.killmails or []),
        "ships_destroyed": totals.get("ships_destroyed", 0),
        "ships_lost": totals.get("ships_lost", 0),
    }


def backfill(fleets, *, zkill=True, **zkill_options) -> dict:
    stats = {"fleets": {}, "zkill": {}}
    if zkill:
        stats["zkill"] = fetch_missed_killmails(fleets, **zkill_options)
    for fleet in fleets:
        try:
            stats["fleets"][fleet.id] = backfill_fleet(fleet, swept=zkill)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Fleet history backfill failed for %s", fleet.id)
            stats["fleets"][fleet.id] = {"error": True}
    return stats
