from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

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


def _top_ship_phrase(ship_counts: dict[str, int], *, limit: int = 3) -> str:
    if not ship_counts:
        return ""
    top = sorted(ship_counts.items(), key=lambda row: -row[1])[:limit]
    return ", ".join(name for name, ship_count in top)


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


def _preview_for_tier(
    tier: dict[str, Any],
    *,
    ship_phrase: str,
    militia: bool,
) -> str:
    previews = tier.get("previews") or {}
    key = "militia" if militia else "generic"
    template = previews.get(key) or tier.get(
        "preview", "Fighting reported on front lines."
    )
    if ship_phrase and "{ships}" in template:
        return template.format(ships=ship_phrase)
    if ship_phrase:
        return f"{template.rstrip('.')} — {ship_phrase}."
    return template


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
    ship_phrase = _top_ship_phrase(ship_counts or {})
    title = tier["generic_title"].format(system=system)
    subheader = _stats_subheader(
        system=system,
        kills=kills,
        pilots=pilots,
        started_at=started_at,
        last_kill_at=last_kill_at,
    )
    preview = _preview_for_tier(tier, ship_phrase=ship_phrase, militia=False)
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
    ship_phrase = _top_ship_phrase(ship_counts or {})
    title = tier["militia_title"].format(faction=faction_label)
    if not is_active and tier["code"] in {"large", "heavy", "major"}:
        title = f"{title} winds down"
    subheader = _stats_subheader(
        system=system,
        kills=kills,
        pilots=pilots,
        started_at=started_at,
        last_kill_at=last_kill_at,
    )
    preview = _preview_for_tier(tier, ship_phrase=ship_phrase, militia=True)
    if not ship_phrase and is_active:
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
            "generic_title": "Small skirmish in {system}",
            "militia_title": "{faction} patrol clash",
            "preview": "Light contact on the front.",
            "previews": {
                "generic": "Brief exchange in {ships}.",
                "militia": "Militia pilots trading blows — {ships}.",
            },
        },
        {
            "code": "medium",
            "min_kills": 14,
            "min_pilots": 12,
            "generic_title": "Medium skirmish in {system}",
            "militia_title": "{faction} skirmish",
            "preview": "Sustained fighting reported.",
            "previews": {
                "generic": "Skirmish escalating — {ships}.",
                "militia": "Enlisted pilots holding the line — {ships}.",
            },
        },
        {
            "code": "large",
            "min_kills": 22,
            "min_pilots": 18,
            "generic_title": "Large skirmish in {system}",
            "militia_title": "{faction} fleet engagement",
            "preview": "Heavy fighting across multiple hull types.",
            "previews": {
                "generic": "Large skirmish brewing — {ships}.",
                "militia": "Organized militia presence — {ships}.",
            },
        },
        {
            "code": "heavy",
            "min_kills": 35,
            "min_pilots": 28,
            "generic_title": "Heavy engagement in {system}",
            "militia_title": "Large {faction} fleet fight",
            "preview": "Major fight with broad ship losses.",
            "previews": {
                "generic": "Heavy engagement underway — {ships}.",
                "militia": "Large organized militia fight — {ships}.",
            },
        },
        {
            "code": "major",
            "min_kills": 50,
            "min_pilots": 40,
            "generic_title": "Major engagement in {system}",
            "militia_title": "Major {faction} operation",
            "preview": "Significant battle on the warzone front.",
            "previews": {
                "generic": "Major engagement — {ships} among the losses.",
                "militia": "Major militia operation — {ships}.",
            },
            "militia_active_preview": "Major militia operation underway on the front.",
        },
    ]
