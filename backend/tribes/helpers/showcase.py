"""Cached public showcase (totals + optional named contributors) for a tribe group.

The showcase runs the group's town-hall report plus its all-time and
best-month highlights, which is far too slow for a page request. Celery
warms every group twice an hour; a request only reads the cache and, on a
miss, queues one refresh and returns a "still being calculated" payload.
"""

from __future__ import annotations

from typing import Any

from app.cache import CachedRollup
from eveonline.models.characters import EvePlayer
from tribes.reports import ReportError, run_group_report
from tribes.reports.period import parse_period
from tribes.reports.registry import HIGHLIGHT_RUNNERS, binding_for_group
from tribes.reports.types import ReportView

SHOWCASE_CACHE_SECONDS = 3600
REFRESH_LOCK_SECONDS = 10 * 60
SHOWCASE_PERIOD = "30d"
# v1: first versioned key; a cached ReportError is {"error": message}.
_SHOWCASE_KEY = "tribes:showcase:v1:{group_id}:{period}"
_LOCK_KEY = "tribes:showcase:refreshing:{group_id}:{period}"
WARMING_MESSAGE = (
    "Group Activity is still being calculated. Check back in a few minutes."
)

# Contributor metric for bindings that don't name one in presentation.
LEGACY_METRIC_KEYS = (
    "kill_count",
    "volume_m3",
    "isk_pi_30d_estimate",
    "delivered_profit",
    "fleet_count",
    "contracts_completed",
)

# Highlight lists that name pilots or quote tickets: roster viewers only.
PRIVATE_HIGHLIGHT_KEYS = frozenset({"welcomed", "fixed"})


def _showcase_presentation(tribe_group) -> dict:
    binding = binding_for_group(tribe_group)
    if not binding:
        return {}
    return binding.presentation.get("showcase", {})


def _numeric_values(row: dict) -> dict[str, float]:
    return {
        key: value
        for key, value in row.items()
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and not key.endswith("_id")
    }


def _enrich_contributors(
    rows: list[dict], metric_key: str | None = None
) -> list[dict[str, Any]]:
    """Attach primary character_id when we can resolve it from the name."""
    names = {
        (row.get("primary_character_name") or "").strip()
        for row in rows
        if row.get("primary_character_name")
        and not row.get("primary_character_id")
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
        char_id = row.get("primary_character_id") or char_id
        key = metric_key or next(
            (k for k in LEGACY_METRIC_KEYS if k in row), None
        )
        metric_value = row.get(key, 0) if key else 0
        if metric_key and not metric_value:
            continue
        contributors.append(
            {
                "character_id": char_id,
                "character_name": char_name or name,
                "metric_key": key or "",
                "metric_value": metric_value,
                "values": _numeric_values(row),
                "row": row,
            }
        )
    return contributors


def _showcase_period(tribe_group) -> str:
    return _showcase_presentation(tribe_group).get("period", SHOWCASE_PERIOD)


def _manual_payload(tribe_group, period: str, message: str) -> dict:
    return {
        "group_id": tribe_group.pk,
        "group_code": tribe_group.code or "",
        "group_name": tribe_group.name,
        "period": period,
        "manual": True,
        "message": message,
        "totals": {},
        "columns": [],
        "contributors": [],
        "highlights": {},
    }


def build_group_showcase(tribe_group) -> dict[str, Any]:
    """
    Run town_hall with roster scope (or program when required). Slow: only
    Celery calls this (see refresh_group_showcase). Always includes totals;
    callers strip contributors and private highlights for guests.
    """
    presentation = _showcase_presentation(tribe_group)
    period = presentation.get("period", SHOWCASE_PERIOD)
    try:
        result = run_group_report(
            tribe_group,
            view=ReportView.TOWN_HALL.value,
            period=period,
            scope="roster",
        )
    except ReportError as exc:
        message = str(exc)
        # Freight / program-only bindings cannot take roster override.
        if "program scope" in message.lower():
            result = run_group_report(
                tribe_group,
                view=ReportView.TOWN_HALL.value,
                period=period,
            )
        elif "no report binding" in message.lower():
            return _manual_payload(tribe_group, period, message)
        else:
            raise

    contributors = (
        []
        if result.manual
        else _enrich_contributors(
            list(result.rows or []), presentation.get("metric")
        )
    )
    return {
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
        "highlights": (
            {} if result.manual else _highlights(tribe_group, period)
        ),
    }


def refresh_group_showcase(tribe_group) -> dict[str, Any]:
    """Recompute and cache one group's showcase (Celery)."""
    try:
        payload = build_group_showcase(tribe_group)
    except ReportError as exc:
        # Cached so the endpoint answers 404 instead of queueing forever.
        payload = {"error": str(exc)}
    SHOWCASE.store(
        payload,
        group_id=tribe_group.pk,
        period=_showcase_period(tribe_group),
    )
    return payload


def group_showcase(tribe_group) -> dict[str, Any]:
    """The cached showcase, or a "still being calculated" payload.

    Never runs the report in the request. Groups without a report (or with
    a manual one) have nothing slow to run, so they are answered directly.
    """
    binding = binding_for_group(tribe_group)
    if binding is None or binding.manual:
        return build_group_showcase(tribe_group)
    period = _showcase_period(tribe_group)
    payload = SHOWCASE.get_or_queue(group_id=tribe_group.pk, period=period)
    if payload is not None:
        return payload
    # manual=True so clients that predate `warming` show the message
    # rather than an empty scoreboard.
    return {
        **_manual_payload(tribe_group, period, WARMING_MESSAGE),
        "warming": True,
    }


def _queue_refresh(group_id: int, **_params) -> None:
    # Imported here: the task module imports this helper.
    from tribes.tasks import (  # pylint: disable=import-outside-toplevel
        refresh_tribe_group_showcase,
    )

    refresh_tribe_group_showcase.apply_async(args=[group_id])


SHOWCASE = CachedRollup(
    key=_SHOWCASE_KEY,
    ttl=SHOWCASE_CACHE_SECONDS,
    lock_key=_LOCK_KEY,
    lock_ttl=REFRESH_LOCK_SECONDS,
    enqueue=_queue_refresh,
)


def _highlights(tribe_group, period: str) -> dict[str, Any]:
    binding = binding_for_group(tribe_group)
    runner = HIGHLIGHT_RUNNERS.get(binding.highlights) if binding else None
    if not runner:
        return {}
    return runner(tribe_group, parse_period(period))


def public_highlights(highlights: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in highlights.items()
        if key not in PRIVATE_HIGHLIGHT_KEYS
    }
