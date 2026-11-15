"""Scheduled upkeep for automatic tasks."""

from app.celery import app
from taskboard import sync


@app.task(expires=15 * 60)
def sync_automatic_tasks():
    """Open, refresh and close every automatic task."""
    return sync.sync_all()


@app.task(expires=60 * 60)
def sweep_tasks():
    """Stop asking, return quiet claims, ask "still needed?"."""
    return sync.sweep()
