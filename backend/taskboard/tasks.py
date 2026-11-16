"""Scheduled upkeep for automatic tasks."""

from app.celery import app
from taskboard import messages, sync


@app.task(expires=15 * 60)
def sync_automatic_tasks():
    """Open, refresh and close every automatic task."""
    return sync.sync_all()


@app.task(expires=15 * 60)
def sync_task_rule(code: str):
    """Re-run one rule after a row it watches changed.

    Queued copies of the same rule collapse into one (AppTask dedupe), so
    approving ten requests in a row is one sync.
    """
    return sync.sync_rule_code(code)


@app.task(expires=60 * 60)
def sweep_tasks():
    """Stop asking, return quiet claims, ask "still needed?"."""
    return sync.sweep()


@app.task(expires=60 * 60)
def send_weekly_task_lists():
    """The weekly list, on the set day and hour (a no-op otherwise)."""
    return messages.send_weekly_lists()


@app.task(expires=60 * 60)
def flush_task_message_holds():
    """Send messages held during pilots' quiet hours once they end."""
    return messages.flush_holds()
