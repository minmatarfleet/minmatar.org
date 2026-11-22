"""
"The week in the alliance" on the homepage (/).

Four tabs, every row of the last 7 days, 12 to a page:

- fights: Fleet activity. Our members' killmails grouped into engagements
  (same constellation, no gap over 20 minutes) with two or more of our pilots,
  so small gangs and unposted fleets show, not just posted fleets.
- kills: every kill and loss line.
- warzone: every warzone site.
- mining: every mining line the ledger syncs saw.

Built from the same event rules as the pulse (alliance.helpers.landing_pulse)
and cached for ten minutes, so paging never recomputes the week.
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import timedelta

from django.utils import timezone

from alliance.helpers.landing_pulse import (
    FACTION_MILITIA_NAMES,
    Event,
    _attacker_sides,
    _biggest,
    _combat_events,
    _entity_names,
    _is_loss,
    _killmail_groups,
    _mining_events,
    _site_events,
    _victim_entity,
    event_rows,
)
from app.cache import CachedRollup
from eveonline.helpers.killmail_text import parse_killmail_list
from eveonline.models import EveCharacterKillmail
from eveuniverse.models import EveSolarSystem
from feed.models import FeedKillmail
from market.helpers.pricing import get_prices_by_type_id

WEEK = CachedRollup(
    key="alliance:landing_week:v2",
    ttl=600,
    lock_key="alliance:landing_week:lock",
    lock_ttl=180,
)

TABS = ("fights", "kills", "warzone", "mining")
PER_PAGE = 12
ENGAGEMENT_GAP = timedelta(minutes=20)


def _our_mails(start, end) -> list[tuple]:
    """(first row, loss?, our pilot ids) per killmail, oldest first."""
    mails = []
    for group in _killmail_groups(start, end).values():
        first = group[0]
        loss = _is_loss(first)
        ours = {r["character__character_id"] for r in group}
        if loss and first["victim_character_id"]:
            ours.add(first["victim_character_id"])
        mails.append((first, loss, ours))
    mails.sort(key=lambda m: m[0]["killmail_time"])
    return mails


def _system_areas(mails) -> dict[int, tuple]:
    return {
        sid: (constellation, region or "")
        for sid, constellation, region in EveSolarSystem.objects.filter(
            id__in={first["solar_system_id"] for first, _, _ in mails}
        ).values_list(
            "id", "eve_constellation_id", "eve_constellation__eve_region__name"
        )
    }


def _clusters(mails, systems) -> list[dict]:
    """Same constellation, no gap over ENGAGEMENT_GAP: one engagement."""
    open_by_area: dict = {}
    clusters: list[dict] = []
    for mail in mails:
        sid = mail[0]["solar_system_id"]
        area = systems.get(sid, (("system", sid), ""))[0]
        when = mail[0]["killmail_time"]
        cluster = open_by_area.get(area)
        if cluster is None or when - cluster["last"] > ENGAGEMENT_GAP:
            cluster = {"first": when, "last": when, "mails": []}
            clusters.append(cluster)
            open_by_area[area] = cluster
        cluster["mails"].append(mail)
        cluster["last"] = when
    return clusters


def _tally(cluster, systems, sides, factions) -> dict:
    tally = {
        "pilots": Counter(),
        "enemies": Counter(),
        "militias": Counter(),
        "regions": Counter(),
        "kills": 0,
    }
    for first, loss, ours in cluster["mails"]:
        tally["pilots"].update(ours)
        tally["regions"][
            systems.get(first["solar_system_id"], (0, ""))[1]
        ] += 1
        if loss:
            side = _biggest(sides.get(first["id"]))
            faction = _biggest(factions.get(first["id"]))
        else:
            tally["kills"] += 1
            side = _victim_entity(first)
            faction = first["victim_faction_id"]
        if side and side[1]:
            tally["enemies"][side] += 1
        elif faction:
            tally["militias"][faction] += 1
    return tally


def _enemy(tally, names) -> tuple[str, str, int]:
    for key, _ in tally["enemies"].most_common():
        if names.get(key[1]):
            return names[key[1]], key[0], key[1]
    if tally["militias"]:
        faction = tally["militias"].most_common(1)[0][0]
        if faction in FACTION_MILITIA_NAMES:
            return FACTION_MILITIA_NAMES[faction], "faction", faction
    return "", "", 0


def _count_items(items, quantities: Counter) -> None:
    for item in items or []:
        # Blueprint copies have no market price.
        if item.get("singleton") != 2 and item.get("item_type_id"):
            quantities[item["item_type_id"]] += (
                item.get("quantity_destroyed") or 0
            ) + (item.get("quantity_dropped") or 0)
        _count_items(item.get("items"), quantities)


def _isk_destroyed(picked) -> dict[int, int]:
    """ISK of the ships we killed in each engagement, valued like zKill:
    hull plus destroyed and dropped items at the baseline guide price."""
    kill_rows = {
        first["id"]: index
        for index, (cluster, _) in enumerate(picked)
        for first, loss, _ in cluster["mails"]
        if not loss
    }
    feed_rows = {
        int(row_id.removeprefix("feed:")): index
        for row_id, index in kill_rows.items()
        if isinstance(row_id, str)
    }
    per_cluster: dict[int, Counter] = {}

    def count(index, ship_type_id, items):
        quantities = per_cluster.setdefault(index, Counter())
        if ship_type_id:
            quantities[ship_type_id] += 1
        _count_items(items, quantities)

    for row_id, ship_type_id, items in EveCharacterKillmail.objects.filter(
        id__in=[r for r in kill_rows if not isinstance(r, str)]
    ).values_list("id", "ship_type_id", "items"):
        count(kill_rows[row_id], ship_type_id, parse_killmail_list(items))
    for killmail_id, ship_type_id, items in FeedKillmail.objects.filter(
        killmail_id__in=list(feed_rows)
    ).values_list(
        "killmail_id", "victim_ship_type_id", "raw_killmail__victim__items"
    ):
        count(feed_rows[killmail_id], ship_type_id, items or [])
    prices = get_prices_by_type_id(
        list({t for q in per_cluster.values() for t in q})
    )
    return {
        index: sum(prices.get(t, 0) * n for t, n in quantities.items())
        for index, quantities in per_cluster.items()
    }


def _engagements(start, end) -> list[Event]:
    mails = _our_mails(start, end)
    if not mails:
        return []
    sides, factions = _attacker_sides(
        [first for first, loss, _ in mails if loss]
    )
    systems = _system_areas(mails)
    picked = []
    for cluster in _clusters(mails, systems):
        tally = _tally(cluster, systems, sides, factions)
        if len(tally["pilots"]) >= 2:
            picked.append((cluster, tally))
    keys = {k for _, tally in picked for k in tally["enemies"]}
    names = _entity_names(
        (k[1] for k in keys if k[0] == "alliance"),
        (k[1] for k in keys if k[0] == "corporation"),
    )
    isk = _isk_destroyed(picked)
    events = []
    for index, (cluster, tally) in enumerate(picked):
        subject, subject_type, subject_id = _enemy(tally, names)
        events.append(
            Event(
                cluster["last"],
                "fight",
                tally["pilots"].most_common(1)[0][0],
                "fought" if subject else "had a fight",
                subject,
                subject_type,
                subject_id,
                others=len(tally["pilots"]) - 1,
                region=tally["regions"].most_common(1)[0][0],
                amount=isk.get(index, 0),
            )
        )
    return events


def build_week(now=None) -> dict:
    now = now or timezone.now()
    start = now - timedelta(days=7)
    sources = {
        "fights": _engagements(start, now),
        "kills": _combat_events(start, now),
        "warzone": _site_events(start, now),
        "mining": _mining_events(start, now),
    }
    tabs = {}
    for tab, events in sources.items():
        events = [e for e in events if e.character_id or e.undisclosed]
        events.sort(key=lambda e: e.occurred_at, reverse=True)
        tabs[tab] = event_rows(events)
    return {"generated_at": now, "tabs": tabs}


def landing_week(tab: str, page: int) -> dict:
    tab = tab if tab in TABS else TABS[0]
    data = WEEK.get_or_compute(build_week)
    rows = data["tabs"].get(tab, [])
    pages = max(1, math.ceil(len(rows) / PER_PAGE))
    page = min(max(1, page), pages)
    return {
        "generated_at": data["generated_at"],
        "tab": tab,
        "page": page,
        "pages": pages,
        "per_page": PER_PAGE,
        "total": len(rows),
        "counts": {t: len(data["tabs"].get(t, [])) for t in TABS},
        "rows": rows[(page - 1) * PER_PAGE : page * PER_PAGE],
    }


__all__ = ["TABS", "PER_PAGE", "build_week", "landing_week"]
