from app.celery import app
from alliance.helpers.health import save_snapshot
from alliance.helpers.snapshot_retention import (
    prune_alliance_health_snapshots,
)


@app.task(name="alliance.tasks.refresh_alliance_health_snapshot")
def refresh_alliance_health_snapshot():
    """Recompute and persist alliance health rollup."""
    snap = save_snapshot()
    return {"id": snap.id, "computed_at": snap.computed_at.isoformat()}


@app.task(name="alliance.tasks.prune_alliance_health_snapshots")
def prune_alliance_health_snapshots_task(dry_run: bool = False):
    """Keep every snapshot from the last 35 days, then one per day."""
    return prune_alliance_health_snapshots(dry_run=dry_run)
