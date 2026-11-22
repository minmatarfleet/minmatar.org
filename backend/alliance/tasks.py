import logging

from django.conf import settings

from app.celery import app
from alliance.helpers.health import save_snapshot
from alliance.helpers.landing_pulse import FAST, build_fast
from alliance.helpers.landing_week import WEEK, build_week
from alliance.helpers.snapshot_retention import (
    prune_alliance_health_snapshots,
)

logger = logging.getLogger(__name__)


@app.task(name="alliance.tasks.refresh_alliance_health_snapshot")
def refresh_alliance_health_snapshot():
    """Recompute and persist alliance health rollup."""
    snap = save_snapshot()
    return {"id": snap.id, "computed_at": snap.computed_at.isoformat()}


@app.task(name="alliance.tasks.prune_alliance_health_snapshots")
def prune_alliance_health_snapshots_task(dry_run: bool = False):
    """Keep every snapshot from the last 35 days, then one per day.

    Deleting needs ALLIANCE_HEALTH_SNAPSHOT_PRUNE_ENABLED; until then the
    task deletes nothing (a dry run still reports the count).
    """
    enabled = getattr(
        settings, "ALLIANCE_HEALTH_SNAPSHOT_PRUNE_ENABLED", False
    )
    if not enabled and not dry_run:
        logger.info(
            "Alliance health snapshot prune skipped: "
            "ALLIANCE_HEALTH_SNAPSHOT_PRUNE_ENABLED is off"
        )
        return 0
    return prune_alliance_health_snapshots(dry_run=dry_run)


@app.task(
    name="alliance.tasks.warm_landing_pages",
    expires=110,
    exclusive=5 * 60,
)
def warm_landing_pages():
    """Rebuild the landing page's week table and Live band every two minutes,
    so new kills show within minutes and no visitor waits on a cold build
    (the week values every kill of seven days: seconds of work)."""
    WEEK.store(build_week())
    FAST.store(build_fast())
