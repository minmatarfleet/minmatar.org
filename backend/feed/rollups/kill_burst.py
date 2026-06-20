from __future__ import annotations

from feed.models import FeedCluster, FeedEvent
from feed.rollups.config import get_rollup_version
from feed.rollups.engagement_copy import build_warzone_engagement_copy
from feed.rollups.types import RollupContext, RollupResult


def _system_name(ctx: RollupContext, solar_system_id: int) -> str:
    return ctx.system_names.get(solar_system_id, f"System {solar_system_id}")


def run_kill_burst_rollup(ctx: RollupContext) -> list[RollupResult]:
    version = get_rollup_version("kill_burst")
    clusters = FeedCluster.objects.filter(
        cluster_type=FeedCluster.ClusterType.KILL_BURST,
        last_kill_at__gte=ctx.since,
        last_kill_at__lte=ctx.until,
    )
    results: list[RollupResult] = []
    for cluster in clusters:
        system = _system_name(ctx, cluster.solar_system_id)
        config = ctx.configs.get("kill_burst", {})
        window = config.get("window_minutes", 15)
        copy = build_warzone_engagement_copy(
            system=system,
            kills=cluster.kill_count,
            pilots=cluster.pilot_count,
            started_at=cluster.started_at,
            last_kill_at=cluster.last_kill_at,
            ship_counts=cluster.ship_counts or {},
        )
        results.append(
            RollupResult(
                kind=FeedEvent.Kind.KILLMAIL_BATCH,
                occurred_at=cluster.last_kill_at,
                title=copy.title,
                subheader=copy.subheader,
                preview=copy.preview,
                body=copy.preview,
                accent=FeedEvent.Accent.COMBAT,
                payload={
                    "system_id": cluster.solar_system_id,
                    "system_name": system,
                    "killmail_count": cluster.kill_count,
                    "window_minutes": window,
                    **copy.payload_extra,
                },
                rollup_code="kill_burst",
                rollup_version=version,
                cluster_key=cluster.cluster_key,
                killmail_ids=cluster.killmail_ids or [],
            )
        )
    return results
