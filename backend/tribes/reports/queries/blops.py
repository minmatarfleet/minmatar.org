"""Black ops hunting: kills and capital-class catches (Fishermen tribe)."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.core.cache import cache
from django.db.models import F
from django.utils import timezone
from eveuniverse.models import EveType

from eveonline.models import EveCharacterKillmailAttacker
from tribes.reports.queries.capitals import _qualifying_ship_type_ids
from tribes.reports.queries.common import (
    best_month,
    best_month_since,
    period_window,
    person_rows,
    roster_characters_by_eve_id,
)
from tribes.reports.roster import roster_user_ids
from tribes.reports.types import PeriodBounds, ReportScope

COLUMNS = ["primary_character_name", "kill_count", "capitals_caught"]

# Biggest first; the order ranks the Biggest catches block.
CATCH_CLASSES = (
    "Titan",
    "Supercarrier",
    "Lancer Dreadnought",
    "Dreadnought",
    "Force Auxiliary",
    "Carrier",
    "Capital Industrial Ship",
    "Capital Ship",
)
CATCH_WINDOW = timedelta(days=366)
CATCHES_SHOWN = 4
# The report and its highlights read the same hunts within one build.
HUNTS_CACHE_SECONDS = 600


def _hunts(tribe_group) -> dict[int, dict]:
    return cache.get_or_set(
        f"tribes:blops-hunts:{tribe_group.pk}",
        lambda: _load_hunts(tribe_group),
        HUNTS_CACHE_SECONDS,
    )


def _load_hunts(tribe_group) -> dict[int, dict]:
    """
    Every kill a roster character got in one of the group's qualifying
    hulls (Redeemer, Sin, Widow, Panther for Fishermen), all time:
    killmail_id -> victim hull, time, victim corp and hunters (user ids).

    One query; the attacker table is large, so filtering happens here
    rather than in several round trips. Killmails come from pilots' ESI
    tokens, so hunts by characters without the killmail scope are missing.
    """
    hulls = _qualifying_ship_type_ids(tribe_group)
    chars = roster_characters_by_eve_id(roster_user_ids(tribe_group))
    if not hulls or not chars:
        return {}
    kills: dict[int, dict] = {}
    for kill_id, ship, at, corp, char_id in (
        EveCharacterKillmailAttacker.objects.filter(
            ship_type_id__in=hulls, character_id__in=chars
        )
        .exclude(character_id=F("killmail__victim_character_id"))
        .values_list(
            "killmail__killmail_id",
            "killmail__ship_type_id",
            "killmail__killmail_time",
            "killmail__victim_corporation_id",
            "character_id",
        )
    ):
        kill = kills.setdefault(
            kill_id,
            {"ship": ship, "at": at, "corp": corp, "hunters": set()},
        )
        kill["hunters"].add(chars[char_id])
    return kills


def _between(kills: dict[int, dict], start, end=None) -> dict[int, dict]:
    return {
        kill_id: kill
        for kill_id, kill in kills.items()
        if kill["at"] >= start and (end is None or kill["at"] <= end)
    }


def _capital_classes(kills: dict[int, dict]) -> dict[int, tuple[str, str]]:
    """Victim hull type id -> (class, hull name) for capital-class hulls."""
    return {
        type_id: (group, name)
        for type_id, group, name in EveType.objects.filter(
            id__in={k["ship"] for k in kills.values()},
            eve_group__name__in=CATCH_CLASSES,
        ).values_list("id", "eve_group__name", "name")
    }


def run_blops_report(
    tribe_group, period: PeriodBounds, scope: ReportScope, params
):
    start, end = period_window(period)
    hunts = _hunts(tribe_group)
    kills = _between(hunts, start, end)
    year = _between(hunts, timezone.now() - CATCH_WINDOW)
    classes = _capital_classes(hunts)

    by_user: dict[int, dict] = defaultdict(
        lambda: {"kill_count": 0, "capitals_caught": 0}
    )
    for kill in kills.values():
        for user_id in kill["hunters"]:
            by_user[user_id]["kill_count"] += 1
    for kill in year.values():
        if kill["ship"] in classes:
            for user_id in kill["hunters"]:
                by_user[user_id]["capitals_caught"] += 1

    totals = {
        "kills": len(kills),
        "hunters": len({u for k in kills.values() for u in k["hunters"]}),
        "capitals_caught_12mo": sum(
            1 for k in year.values() if k["ship"] in classes
        ),
        "supers_titans_all_time": sum(
            1
            for k in hunts.values()
            if classes.get(k["ship"], ("",))[0] in ("Titan", "Supercarrier")
        ),
    }
    return person_rows(by_user, "kill_count"), totals, COLUMNS


def blops_highlights(tribe_group, period: PeriodBounds) -> dict:
    hunts = _hunts(tribe_group)
    year = _between(hunts, timezone.now() - CATCH_WINDOW)
    classes = _capital_classes(hunts)
    rank = {name: i for i, name in enumerate(CATCH_CLASSES)}
    catches = sorted(
        (
            (kill_id, kill)
            for kill_id, kill in year.items()
            if kill["ship"] in classes
        ),
        key=lambda item: (
            rank[classes[item[1]["ship"]][0]],
            -item[1]["at"].timestamp(),
        ),
    )[:CATCHES_SHOWN]

    caught_ever = [
        classes[k["ship"]][0] for k in hunts.values() if k["ship"] in classes
    ]
    return {
        "catches": [
            {
                "killmail_id": kill_id,
                "ship_type_id": kill["ship"],
                "ship_name": classes[kill["ship"]][1],
                "ship_class": classes[kill["ship"]][0],
                "victim_corporation_id": kill["corp"],
                "killed_at": kill["at"].isoformat(),
                "hunters": len(kill["hunters"]),
            }
            for kill_id, kill in catches
        ],
        "best_month": best_month(
            (kill["at"], 1)
            for kill in _between(hunts, best_month_since()).values()
        ),
        "all_time": {
            "titans": caught_ever.count("Titan"),
            "supers": caught_ever.count("Supercarrier"),
            "capitals": len(caught_ever),
        },
    }
