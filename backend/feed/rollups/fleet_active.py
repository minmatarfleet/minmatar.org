from __future__ import annotations

from datetime import datetime, timedelta

from feed.constants import FACTION_AMARR, FACTION_MINMATAR
from feed.helpers.killmail_classify import (
    dominant_attacker_faction,
    faction_to_accent_key,
)
from feed.helpers.eve_names import sample_fleet_roster
from feed.models import FeedCluster, FeedEvent, FeedKillmail
from feed.rollups.config import get_rollup_config, get_rollup_version
from feed.rollups.engagement_copy import build_militia_engagement_copy
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


def _dominant_faction_for_cluster(cluster: FeedCluster) -> int | None:
    killmail_ids = cluster.killmail_ids or []
    if not killmail_ids:
        return None
    raw = list(
        FeedKillmail.objects.filter(killmail_id__in=killmail_ids).values_list(
            "raw_killmail", flat=True
        )
    )
    fleet_cfg = get_rollup_config("fleet_active")
    return dominant_attacker_faction(
        raw,
        threshold=fleet_cfg.get("dominant_faction_threshold", 0.75),
    )


def _collapse_fleet_clusters(
    clusters,
) -> list[tuple[FeedCluster, datetime, int | None]]:
    """Merge adjacent time-bucket splits of the same fight into one cluster."""
    stale_minutes = get_rollup_config("fleet_active").get("stale_minutes", 20)
    stale_delta = timedelta(minutes=stale_minutes)
    chains: list[list[tuple[FeedCluster, int | None]]] = []
    for cluster in sorted(
        clusters,
        key=lambda row: (
            row.solar_system_id,
            row.started_at,
        ),
    ):
        faction = _dominant_faction_for_cluster(cluster)
        placed = False
        for chain in chains:
            last_cluster, last_faction = chain[-1]
            if (
                last_cluster.solar_system_id == cluster.solar_system_id
                and last_faction == faction
                and cluster.started_at
                <= last_cluster.last_kill_at + stale_delta
            ):
                chain.append((cluster, faction))
                placed = True
                break
        if not placed:
            chains.append([(cluster, faction)])

    collapsed: list[tuple[FeedCluster, datetime, int | None]] = []
    for chain in chains:
        representative = max(chain, key=lambda row: row[0].last_kill_at)[0]
        engagement_start = min(row[0].started_at for row in chain)
        faction = _dominant_faction_for_cluster(representative)
        collapsed.append((representative, engagement_start, faction))
    return collapsed


def _fleet_event_cluster_key(
    cluster: FeedCluster,
    *,
    engagement_start: datetime,
    faction_id: int | None,
) -> str:
    started = engagement_start.replace(second=0, microsecond=0)
    faction = faction_id if faction_id is not None else 0
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
    best_by_key: dict[str, tuple[FeedCluster, int | None]] = {}
    engagement_start_by_key: dict[str, datetime] = {}
    for cluster, engagement_start, faction_id in _collapse_fleet_clusters(
        clusters
    ):
        key = _fleet_event_cluster_key(
            cluster,
            engagement_start=engagement_start,
            faction_id=faction_id,
        )
        prev = best_by_key.get(key)
        if prev is None or cluster.last_kill_at > prev[0].last_kill_at:
            best_by_key[key] = (cluster, faction_id)
            engagement_start_by_key[key] = engagement_start

    for key, (cluster, faction_id) in best_by_key.items():
        if faction_id is None or cluster.pilot_count <= 5:
            continue
        system = _system_name(ctx, cluster.solar_system_id)
        engagement_start = engagement_start_by_key[key]
        copy = build_militia_engagement_copy(
            faction_label=_faction_label(faction_id),
            system=system,
            kills=cluster.kill_count,
            pilots=cluster.pilot_count,
            started_at=engagement_start,
            last_kill_at=cluster.last_kill_at,
            ship_counts=cluster.ship_counts or {},
            is_active=cluster.is_active,
        )
        roster, roster_total = sample_fleet_roster(
            cluster.attacker_ids,
            faction_id=faction_id,
            limit=8,
        )
        faction_key = faction_to_accent_key(faction_id)
        results.append(
            RollupResult(
                kind=FeedEvent.Kind.FLEET_ACTIVE,
                occurred_at=cluster.last_kill_at,
                title=copy.title,
                subheader=copy.subheader,
                preview=copy.preview,
                body=copy.preview,
                accent=_accent_for_faction(faction_id),
                payload={
                    "faction": faction_key,
                    "system_id": cluster.solar_system_id,
                    "system_name": system,
                    "related_cluster_key": cluster.cluster_key,
                    "roster": roster,
                    "roster_total": roster_total,
                    **copy.payload_extra,
                },
                rollup_code="fleet_active",
                rollup_version=version,
                cluster_key=key,
                is_active=cluster.is_active,
                killmail_ids=cluster.killmail_ids or [],
            )
        )
    return results
