"""The recent intel timeline: pilot reports plus the feed's pings.

One list for everyone (no per-viewer filtering), so it is built at most
once per ``RECENT_CACHE_SECONDS`` however many desktop apps poll it, and
dropped as soon as someone shares a report. Jumps from the viewer are
worked out in the app from the intel map, so the viewer's location never
reaches the server.
"""

from __future__ import annotations

from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

from feed.models import FeedAmarrFleetAlert, FeedCapitalAlert
from intel.models import IntelReport
from intel.services.local import (
    AMARR_FACTION_ID,
    FRIENDLY,
    HOSTILE,
    MINMATAR_FACTION_ID,
    NEUTRAL,
)
from intel.services.ships import ship_list

RECENT_MINUTES = 120
RECENT_CACHE_KEY = "intel:recent:v1"
RECENT_CACHE_SECONDS = 15
MAX_ITEMS = 150
MAX_SHIPS = 12  # per row: the app shows 4 and puts the rest behind "+N"


def invalidate_recent() -> None:
    cache.delete(RECENT_CACHE_KEY)


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def report_summary_line(report: IntelReport) -> str:
    summary = report.summary or {}
    if report.kind == IntelReport.Kind.DSCAN:
        parts = [_plural(summary.get("ships", 0), "ship")]
        if summary.get("capsules"):
            parts.append(_plural(summary["capsules"], "capsule"))
        if summary.get("other"):
            parts.append(f"{summary['other']} other")
        return " · ".join(parts)
    line = _plural(summary.get("pilots", 0), "pilot")
    if summary.get("resolved"):
        standings = summary.get("standings") or {}
        sides = [
            f"{standings.get(side, 0)} {side}"
            for side in (HOSTILE, NEUTRAL, FRIENDLY)
            if standings.get(side)
        ]
        if sides:
            line += " · " + ", ".join(sides)
        # The biggest bloc we're sure of, from the affiliation database.
        sure = [b for b in summary.get("blocs") or [] if not b.get("likely")]
        if sure:
            line += f" · {sure[0]['count']} {sure[0]['name']}"
    return line


def _local_image(summary: dict) -> dict | None:
    standings = summary.get("standings") or {}
    if not summary.get("resolved") or not any(standings.values()):
        return None
    top = max(standings, key=lambda side: standings[side])
    if top == HOSTILE:
        return {"kind": "faction", "id": AMARR_FACTION_ID}
    if top == FRIENDLY:
        return {"kind": "faction", "id": MINMATAR_FACTION_ID}
    return None


def report_item(report: IntelReport) -> dict:
    summary = report.summary or {}
    is_dscan = report.kind == IntelReport.Kind.DSCAN
    hulls = summary.get("hulls") or []
    if is_dscan:
        top = max(hulls, key=lambda h: h["count"]) if hulls else None
        image = {"kind": "type", "id": top["type_id"]} if top else None
    else:
        image = _local_image(summary)
    return {
        "id": f"r:{report.public_id}",
        "kind": report.kind,
        "is_ping": False,
        "report_id": report.public_id,
        "system_id": report.solar_system_id,
        "system_name": report.system_name,
        "occurred_at": report.created_at,
        "source": report.reporter_name or "Unknown pilot",
        "note": report.note,
        "count": summary.get("ships") if is_dscan else summary.get("pilots"),
        "summary": report_summary_line(report),
        "image": image,
        "ships": [
            {k: h[k] for k in ("type_id", "name", "count")}
            for h in hulls[:MAX_SHIPS]
        ],
        "standings": None if is_dscan else summary.get("standings"),
    }


def _capital_label(capitals: list[dict]) -> str:
    labels = []
    for entry in capitals[:3]:
        count = int(entry.get("count") or 1)
        name = entry.get("name") or f"Type {entry.get('type_id')}"
        labels.append(f"{count} {name}" if count > 1 else name)
    return " + ".join(labels) or "Capitals"


def capital_item(alert: FeedCapitalAlert) -> dict:
    composition = alert.composition or {}
    ships = ship_list(composition.get("ship_counts"))
    if not ships:
        ships = ship_list(
            {
                entry["type_id"]: entry.get("count") or 1
                for entry in alert.capitals or []
                if entry.get("type_id")
            }
        )
    capitals = alert.capitals or []
    kills = len(alert.kills or [])
    image_type = (capitals[0].get("type_id") if capitals else None) or (
        ships[0]["type_id"] if ships else None
    )
    return {
        "id": f"c:{alert.pk}",
        "kind": "caps",
        "is_ping": True,
        "report_id": None,
        "system_id": alert.solar_system_id,
        "system_name": alert.system_name,
        "occurred_at": alert.last_activity_at,
        "source": "Feed",
        "note": "",
        "count": None,
        "summary": (
            f"{_capital_label(capitals)} · {alert.distance_ly:.1f} ly "
            f"from Amamake · {_plural(kills, 'kill')}"
        ),
        "image": {"kind": "type", "id": image_type} if image_type else None,
        "ships": [
            {k: h[k] for k in ("type_id", "name", "count")}
            for h in ships[:MAX_SHIPS]
        ],
        "standings": None,
    }


def fleet_item(alert: FeedAmarrFleetAlert) -> dict:
    ships = ship_list(alert.ship_counts)
    parts = [
        f"Amarr fleet · ~{alert.pilots} pilots",
        _plural(alert.kills, "kill"),
    ]
    systems = alert.systems or []
    if len(systems) > 1:
        parts.append(f"moved from {systems[-2].get('system_name')}")
    image = (
        {"kind": "type", "id": ships[0]["type_id"]}
        if ships
        else {"kind": "faction", "id": AMARR_FACTION_ID}
    )
    return {
        "id": f"f:{alert.pk}",
        "kind": "fleet",
        "is_ping": True,
        "report_id": None,
        "system_id": alert.solar_system_id,
        "system_name": alert.system_name,
        "occurred_at": alert.fight_at or alert.last_activity_at,
        "source": "Feed",
        "note": "",
        "count": alert.pilots,
        "summary": " · ".join(parts),
        "image": image,
        "ships": [
            {k: h[k] for k in ("type_id", "name", "count")}
            for h in ships[:MAX_SHIPS]
        ],
        "standings": None,
    }


def _build_recent() -> dict:
    now = timezone.now()
    since = now - timedelta(minutes=RECENT_MINUTES)
    items = [
        report_item(report)
        for report in IntelReport.objects.filter(created_at__gte=since)
        .defer("raw")
        .order_by("-created_at")[:MAX_ITEMS]
    ]
    items += [
        capital_item(alert)
        for alert in FeedCapitalAlert.objects.filter(
            last_activity_at__gte=since
        ).defer("discord_messages")[:MAX_ITEMS]
    ]
    items += [
        fleet_item(alert)
        for alert in FeedAmarrFleetAlert.objects.filter(
            last_activity_at__gte=since
        ).defer("discord_messages", "roster")[:MAX_ITEMS]
    ]
    items.sort(key=lambda item: item["occurred_at"], reverse=True)
    return {
        "items": items[:MAX_ITEMS],
        "window_minutes": RECENT_MINUTES,
        "generated_at": now,
    }


def recent_intel() -> dict:
    data = cache.get(RECENT_CACHE_KEY)
    if data is None:
        data = _build_recent()
        cache.set(RECENT_CACHE_KEY, data, RECENT_CACHE_SECONDS)
    return data
