"""Cached public showcase (totals + optional named contributors) for a tribe group."""

from __future__ import annotations

from typing import Any

from django.core.cache import cache

from eveonline.models.characters import EvePlayer
from tribes.reports import ReportError, run_group_report
from tribes.reports.types import ReportView

SHOWCASE_CACHE_SECONDS = 3600
SHOWCASE_PERIOD = "30d"


def _cache_key(group_id: int) -> str:
    return f"tribes:showcase:{group_id}:{SHOWCASE_PERIOD}"


def _enrich_contributors(rows: list[dict]) -> list[dict[str, Any]]:
    """Attach primary character_id when we can resolve it from the name."""
    names = {
        (row.get("primary_character_name") or "").strip()
        for row in rows
        if row.get("primary_character_name")
    }
    name_to_char: dict[str, tuple[int, str]] = {}
    if names:
        for player in EvePlayer.objects.filter(
            primary_character__character_name__in=names
        ).select_related("primary_character"):
            char = player.primary_character
            if char and char.character_name:
                name_to_char[char.character_name] = (
                    char.character_id,
                    char.character_name,
                )

    contributors: list[dict[str, Any]] = []
    for row in rows:
        name = (row.get("primary_character_name") or "").strip()
        char_id, char_name = name_to_char.get(name, (None, name))
        metric_key = next(
            (
                k
                for k in (
                    "kill_count",
                    "volume_m3",
                    "isk_pi_30d_estimate",
                    "delivered_margin",
                    "fleet_count",
                    "contracts_completed",
                )
                if k in row
            ),
            None,
        )
        metric_value = row.get(metric_key, 0) if metric_key else 0
        contributors.append(
            {
                "character_id": char_id,
                "character_name": char_name or name,
                "metric_key": metric_key or "",
                "metric_value": metric_value,
                "row": row,
            }
        )
    return contributors


def build_group_showcase(tribe_group) -> dict[str, Any]:
    """
    Run town_hall with roster scope (or program when required).
    Cached ~1h. Always includes totals; callers strip contributors for guests.
    """
    key = _cache_key(tribe_group.pk)
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        result = run_group_report(
            tribe_group,
            view=ReportView.TOWN_HALL.value,
            period=SHOWCASE_PERIOD,
            scope="roster",
        )
    except ReportError as exc:
        message = str(exc)
        # Freight / program-only bindings cannot take roster override.
        if "program scope" in message.lower():
            result = run_group_report(
                tribe_group,
                view=ReportView.TOWN_HALL.value,
                period=SHOWCASE_PERIOD,
            )
        elif "no report binding" in message.lower():
            payload = {
                "group_id": tribe_group.pk,
                "group_code": tribe_group.code or "",
                "group_name": tribe_group.name,
                "period": SHOWCASE_PERIOD,
                "manual": True,
                "message": message,
                "totals": {},
                "columns": [],
                "contributors": [],
            }
            cache.set(key, payload, SHOWCASE_CACHE_SECONDS)
            return payload
        else:
            raise

    contributors = (
        [] if result.manual else _enrich_contributors(list(result.rows or []))
    )
    payload = {
        "group_id": result.group_id,
        "group_code": result.group_code,
        "group_name": result.group_name,
        "period": result.period,
        "period_start": result.period_start.isoformat(),
        "period_end": result.period_end.isoformat(),
        "manual": result.manual,
        "message": result.message,
        "totals": result.totals or {},
        "columns": result.columns or [],
        "contributors": contributors,
    }
    cache.set(key, payload, SHOWCASE_CACHE_SECONDS)
    return payload
