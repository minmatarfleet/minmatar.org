from app.celery import app
from alliance.helpers.health import save_snapshot


@app.task(name="alliance.tasks.refresh_alliance_health_snapshot")
def refresh_alliance_health_snapshot():
    """Recompute and persist alliance health rollup."""
    snap = save_snapshot()
    return {"id": snap.id, "computed_at": snap.computed_at.isoformat()}
