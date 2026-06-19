from __future__ import annotations

from feed.models import FeedCluster, FeedEvent
from feed.rollups.config import get_rollup_version
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
        preview = f"Kill burst reported in {system}."
        if cluster.ship_counts:
            top_ships = ", ".join(list(cluster.ship_counts.keys())[:3])
            preview = f"Heavy fighting — {top_ships}."
        results.append(
            RollupResult(
                kind=FeedEvent.Kind.KILLMAIL_BATCH,
                occurred_at=cluster.last_kill_at,
                title=f"{cluster.kill_count} killmails in {window} min",
                subheader=system,
                preview=preview,
                body=preview,
                accent=FeedEvent.Accent.COMBAT,
                payload={
                    "system_id": cluster.solar_system_id,
                    "system_name": system,
                    "killmail_count": cluster.kill_count,
                    "window_minutes": window,
                },
                rollup_code="kill_burst",
                rollup_version=version,
                cluster_key=cluster.cluster_key,
                killmail_ids=cluster.killmail_ids or [],
            )
        )
    return results
