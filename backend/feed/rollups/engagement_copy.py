from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from feed.helpers.eve_names import (
    format_hull_classes_phrase,
    top_ships_from_counts,
)
from feed.rollups.config import get_rollup_config


@dataclass(frozen=True)
class EngagementCopy:
    tier: str
    title: str
    subheader: str
    preview: str
    payload_extra: dict[str, Any]


def _engagement_config() -> dict[str, Any]:
    return get_rollup_config("engagement_copy")


def _duration_minutes(started_at: datetime, last_kill_at: datetime) -> int:
    delta = last_kill_at - started_at
    return max(1, int(delta.total_seconds() // 60))


def _ships_payload(
    ship_counts: dict[str, int] | None,
) -> list[dict[str, int | str]]:
    return [
        {"name": ship["name"], "count": ship["count"]}
        for ship in top_ships_from_counts(ship_counts)
    ]


def _resolve_tier(kills: int, pilots: int) -> dict[str, Any]:
    cfg = _engagement_config()
    tiers = cfg.get("tiers") or _default_tiers()
    matched = tiers[0]
    for tier in tiers:
        if kills >= tier["min_kills"] or pilots >= tier["min_pilots"]:
            matched = tier
    return matched


def _stats_subheader(
    *,
    system: str,
    kills: int,
    pilots: int,
    started_at: datetime,
    last_kill_at: datetime,
) -> str:
    duration = _duration_minutes(started_at, last_kill_at)
    parts = [system, f"{kills} kills"]
    if pilots:
        parts.append(f"{pilots} pilots")
    parts.append(f"~{duration}m")
    return " · ".join(parts)


def _skirmish_preview(
    tier: dict[str, Any],
    *,
    ship_counts: dict[str, int] | None,
) -> str:
    size = tier.get("militia_size", tier["code"].title())
    hull_phrase = format_hull_classes_phrase(ship_counts)
    if hull_phrase:
        return f"{size} skirmish involving {hull_phrase}."
    return tier.get("preview", "Fighting reported on front lines.")


def build_warzone_engagement_copy(
    *,
    system: str,
    kills: int,
    pilots: int,
    started_at: datetime,
    last_kill_at: datetime,
    ship_counts: dict[str, int] | None = None,
) -> EngagementCopy:
    tier = _resolve_tier(kills, pilots)
    title = tier["generic_title"].format(system=system)
    subheader = _stats_subheader(
        system=system,
        kills=kills,
        pilots=pilots,
        started_at=started_at,
        last_kill_at=last_kill_at,
    )
    preview = _skirmish_preview(tier, ship_counts=ship_counts)
    duration = _duration_minutes(started_at, last_kill_at)
    return EngagementCopy(
        tier=tier["code"],
        title=title,
        subheader=subheader,
        preview=preview,
        payload_extra={
            "engagement_tier": tier["code"],
            "engagement_label": tier["generic_title"].format(system=system),
            "kills": kills,
            "pilots": pilots,
            "duration_minutes": duration,
            "ships": _ships_payload(ship_counts),
        },
    )


def build_militia_engagement_copy(
    *,
    faction_label: str,
    system: str,
    kills: int,
    pilots: int,
    started_at: datetime,
    last_kill_at: datetime,
    ship_counts: dict[str, int] | None = None,
    is_active: bool = True,
) -> EngagementCopy:
    tier = _resolve_tier(kills, pilots)
    size_label = tier.get("militia_size", tier["code"].title())
    title = tier["militia_title"].format(
        faction=faction_label,
        size=size_label,
    )
    if not is_active and tier["code"] in {"large", "heavy", "major"}:
        title = f"{title} winds down"
    subheader = _stats_subheader(
        system=system,
        kills=kills,
        pilots=pilots,
        started_at=started_at,
        last_kill_at=last_kill_at,
    )
    preview = _skirmish_preview(tier, ship_counts=ship_counts)
    if not ship_counts and is_active:
        preview = tier.get("militia_active_preview", preview)
    duration = _duration_minutes(started_at, last_kill_at)
    return EngagementCopy(
        tier=tier["code"],
        title=title,
        subheader=subheader,
        preview=preview,
        payload_extra={
            "engagement_tier": tier["code"],
            "engagement_label": title,
            "kills": kills,
            "pilots": pilots,
            "duration_minutes": duration,
            "is_active": is_active,
        },
    )


def _default_tiers() -> list[dict[str, Any]]:
    return [
        {
            "code": "small",
            "min_kills": 8,
            "min_pilots": 6,
            "militia_size": "Small",
            "generic_title": "Small skirmish in {system}",
            "militia_title": "{size} {faction} fleet active",
            "preview": "Light contact on the front.",
            "militia_active_preview": "Small militia fleet active on the front.",
        },
        {
            "code": "medium",
            "min_kills": 14,
            "min_pilots": 12,
            "militia_size": "Medium",
            "generic_title": "Medium skirmish in {system}",
            "militia_title": "{size} {faction} fleet active",
            "preview": "Sustained fighting reported.",
            "militia_active_preview": "Medium militia fleet active on the front.",
        },
        {
            "code": "large",
            "min_kills": 22,
            "min_pilots": 18,
            "militia_size": "Large",
            "generic_title": "Large skirmish in {system}",
            "militia_title": "{size} {faction} fleet active",
            "preview": "Heavy fighting across multiple hull types.",
            "militia_active_preview": "Large militia fleet active on the front.",
        },
        {
            "code": "heavy",
            "min_kills": 35,
            "min_pilots": 28,
            "militia_size": "Heavy",
            "generic_title": "Heavy engagement in {system}",
            "militia_title": "{size} {faction} fleet active",
            "preview": "Major fight with broad ship losses.",
            "militia_active_preview": "Heavy militia fleet active on the front.",
        },
        {
            "code": "major",
            "min_kills": 50,
            "min_pilots": 40,
            "militia_size": "Major",
            "generic_title": "Major engagement in {system}",
            "militia_title": "{size} {faction} fleet active",
            "preview": "Significant battle on the warzone front.",
            "militia_active_preview": "Major militia fleet active on the front.",
        },
    ]
