from __future__ import annotations

from feed.constants import FACTION_AMARR, FACTION_MINMATAR
from feed.helpers.killmail_classify import faction_to_accent_key
from feed.models import FeedCluster, FeedEvent
from feed.rollups.config import get_rollup_version
from feed.rollups.types import RollupContext, RollupResult


def _system_name(ctx: RollupContext, solar_system_id: int) -> str:
    return ctx.system_names.get(solar_system_id, f"System {solar_system_id}")


def _faction_label(faction_id: int | None) -> str:
    if faction_id == FACTION_MINMATAR:
        return "Minmatar"
    if faction_id == FACTION_AMARR:
        return "Amarr"
    return "Pirate"


def _accent_for_faction(faction_id: int | None) -> str:
    key = faction_to_accent_key(faction_id)
    if key == "minmatar":
        return FeedEvent.Accent.MILITIA
    if key == "amarr":
        return FeedEvent.Accent.AMARR
    return FeedEvent.Accent.COMBAT


def run_fleet_active_rollup(ctx: RollupContext) -> list[RollupResult]:
    version = get_rollup_version("fleet_active")
    clusters = FeedCluster.objects.filter(
        cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT,
        last_kill_at__gte=ctx.since,
        last_kill_at__lte=ctx.until,
    )
    results: list[RollupResult] = []
    for cluster in clusters:
        system = _system_name(ctx, cluster.solar_system_id)
        faction_label = _faction_label(cluster.dominant_faction_id)
        composition = ""
        if cluster.ship_counts:
            composition = ", ".join(list(cluster.ship_counts.keys())[:5])
        title = f"{faction_label} fleet active"
        if cluster.dominant_faction_id is None:
            title = "Fleet active"
        subheader = f"{system} · {cluster.kill_count} kills · {cluster.pilot_count} pilots"
        preview = composition or "Active on front lines."
        faction_key = faction_to_accent_key(cluster.dominant_faction_id)
        results.append(
            RollupResult(
                kind=FeedEvent.Kind.FLEET_ACTIVE,
                occurred_at=cluster.last_kill_at,
                title=title,
                subheader=subheader,
                preview=preview,
                body=composition,
                accent=_accent_for_faction(cluster.dominant_faction_id),
                payload={
                    "faction": faction_key,
                    "system_id": cluster.solar_system_id,
                    "system_name": system,
                    "kills": cluster.kill_count,
                    "pilots": cluster.pilot_count,
                    "is_active": cluster.is_active,
                    "related_cluster_key": cluster.cluster_key,
                },
                rollup_code="fleet_active",
                rollup_version=version,
                cluster_key=cluster.cluster_key,
                is_active=cluster.is_active,
                killmail_ids=cluster.killmail_ids or [],
            )
        )
    return results
