from __future__ import annotations

from datetime import datetime
from typing import Callable

from feed.models import FeedMonitoredSystem, FeedRollupConfig
from feed.rollups.config import get_rollup_config
from feed.rollups.fleet_active import run_fleet_active_rollup
from feed.rollups.kill_burst import run_kill_burst_rollup
from feed.rollups.militia_joins import run_militia_joins_rollup
from feed.rollups.types import RollupContext, RollupResult

RollupProcessor = Callable[[RollupContext], list[RollupResult]]

ROLLUP_PROCESSORS: dict[str, RollupProcessor] = {
    "kill_burst": run_kill_burst_rollup,
    "fleet_active": run_fleet_active_rollup,
    "militia_joins": run_militia_joins_rollup,
}


def build_context(since: datetime, until: datetime) -> RollupContext:
    configs = {code: get_rollup_config(code) for code in ROLLUP_PROCESSORS}
    system_names = {
        row.solar_system_id: row.name
        for row in FeedMonitoredSystem.objects.filter(is_active=True)
    }
    return RollupContext(
        since=since,
        until=until,
        configs=configs,
        system_names=system_names,
    )


def run_rollup(rollup_code: str, ctx: RollupContext) -> list[RollupResult]:
    processor = ROLLUP_PROCESSORS.get(rollup_code)
    if processor is None:
        return []
    try:
        row = FeedRollupConfig.objects.get(rollup_code=rollup_code)
        if not row.is_enabled:
            return []
    except FeedRollupConfig.DoesNotExist:
        pass
    return processor(ctx)


def run_all_rollups(
    ctx: RollupContext, *, codes: list[str] | None = None
) -> list[RollupResult]:
    results: list[RollupResult] = []
    for code in codes or list(ROLLUP_PROCESSORS.keys()):
        results.extend(run_rollup(code, ctx))
    return results
