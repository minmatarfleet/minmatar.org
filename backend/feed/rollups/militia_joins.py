from __future__ import annotations

from datetime import timedelta

from django.db.models import Count

from feed.constants import FACTION_AMARR, FACTION_MINMATAR
from feed.helpers.killmail_classify import faction_to_label
from feed.models import FeedEvent, FeedMilitiaFirstSeen
from feed.rollups.config import get_rollup_version
from feed.rollups.types import RollupContext, RollupResult


def _faction_payload_key(faction_id: int) -> str:
    if faction_id == FACTION_MINMATAR:
        return "minmatar"
    if faction_id == FACTION_AMARR:
        return "amarr"
    return "unknown"


def _accent_for_faction(faction_id: int) -> str:
    if faction_id == FACTION_MINMATAR:
        return FeedEvent.Accent.MILITIA
    if faction_id == FACTION_AMARR:
        return FeedEvent.Accent.AMARR
    return FeedEvent.Accent.COMBAT


def run_militia_joins_rollup(ctx: RollupContext) -> list[RollupResult]:
    version = get_rollup_version("militia_joins")
    config = ctx.configs.get("militia_joins", {})
    hourly_min = config.get("hourly_min_count", 5)
    daily_min = config.get("daily_min_count", 15)
    now = ctx.until

    results: list[RollupResult] = []
    for window_hours, min_count, suffix in (
        (config.get("hourly_window_hours", 1), hourly_min, "1h"),
        (config.get("daily_window_hours", 24), daily_min, "24h"),
    ):
        window_start = now - timedelta(hours=window_hours)
        grouped = (
            FeedMilitiaFirstSeen.objects.filter(
                first_seen_at__gte=window_start,
                first_seen_at__lte=now,
            )
            .values("faction_id")
            .annotate(count=Count("id"))
        )
        for row in grouped:
            count = row["count"]
            if count < min_count:
                continue
            faction_id = row["faction_id"]
            cluster_key = f"militia:{faction_id}:{suffix}:{window_start.strftime('%Y%m%dT%H')}"
            results.append(
                RollupResult(
                    kind=FeedEvent.Kind.MILITIA_JOINS,
                    occurred_at=now,
                    title=f"{count} pilots newly active in warzone",
                    subheader=faction_to_label(faction_id),
                    preview="Pilots newly appearing in monitored warzone killmails.",
                    body="",
                    accent=_accent_for_faction(faction_id),
                    payload={
                        "proxy": True,
                        "faction": _faction_payload_key(faction_id),
                        "join_count": count,
                        "window_hours": window_hours,
                    },
                    rollup_code="militia_joins",
                    rollup_version=version,
                    cluster_key=cluster_key,
                )
            )
    return results
