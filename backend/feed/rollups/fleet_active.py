from __future__ import annotations

from datetime import datetime, timedelta

from feed.constants import FACTION_AMARR, FACTION_MINMATAR
from feed.helpers.killmail_classify import faction_to_accent_key
from feed.models import FeedCluster, FeedEvent
from feed.rollups.config import get_rollup_config, get_rollup_version
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


def _collapse_fleet_clusters(
    clusters,
) -> list[tuple[FeedCluster, datetime]]:
    """Merge adjacent time-bucket splits of the same fight into one cluster."""
    stale_minutes = get_rollup_config("fleet_active").get("stale_minutes", 20)
    stale_delta = timedelta(minutes=stale_minutes)
    chains: list[list[FeedCluster]] = []
    for cluster in sorted(
        clusters,
        key=lambda row: (
            row.solar_system_id,
            row.dominant_faction_id or 0,
            row.started_at,
        ),
    ):
        faction = cluster.dominant_faction_id or 0
        placed = False
        for chain in chains:
            last = chain[-1]
            if (
                last.solar_system_id == cluster.solar_system_id
                and (last.dominant_faction_id or 0) == faction
                and cluster.started_at <= last.last_kill_at + stale_delta
            ):
                chain.append(cluster)
                placed = True
                break
        if not placed:
            chains.append([cluster])

    collapsed: list[tuple[FeedCluster, datetime]] = []
    for chain in chains:
        representative = max(chain, key=lambda row: row.last_kill_at)
        engagement_start = min(row.started_at for row in chain)
        collapsed.append((representative, engagement_start))
    return collapsed


def _fleet_event_cluster_key(
    cluster: FeedCluster, *, engagement_start: datetime
) -> str:
    started = engagement_start.replace(second=0, microsecond=0)
    faction = cluster.dominant_faction_id or 0
    return (
        f"fleet_active:{cluster.solar_system_id}:{faction}:"
        f"{started.strftime('%Y-%m-%dT%H:%M')}"
    )


def run_fleet_active_rollup(ctx: RollupContext) -> list[RollupResult]:
    version = get_rollup_version("fleet_active")
    clusters = FeedCluster.objects.filter(
        cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT,
        last_kill_at__gte=ctx.since,
        last_kill_at__lte=ctx.until,
    )
    results: list[RollupResult] = []
    best_by_key: dict[str, FeedCluster] = {}
    engagement_start_by_key: dict[str, datetime] = {}
    for cluster, engagement_start in _collapse_fleet_clusters(clusters):
        key = _fleet_event_cluster_key(
            cluster, engagement_start=engagement_start
        )
        prev = best_by_key.get(key)
        if prev is None or cluster.last_kill_at > prev.last_kill_at:
            best_by_key[key] = cluster
            engagement_start_by_key[key] = engagement_start

    for key, cluster in best_by_key.items():
        engagement_start = engagement_start_by_key[key]
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
                cluster_key=key,
                is_active=cluster.is_active,
                killmail_ids=cluster.killmail_ids or [],
            )
        )
    return results
