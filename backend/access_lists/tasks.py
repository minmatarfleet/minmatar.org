import logging

from app.celery import app
from eveonline.utils import get_esi_downtime_countdown

from access_lists.helpers import sync_executor_access_lists

logger = logging.getLogger(__name__)


@app.task
def sync_executor_access_lists_task():
    """Sync in-game access lists from the executor character."""
    countdown = get_esi_downtime_countdown()
    if countdown > 0:
        sync_executor_access_lists_task.apply_async(countdown=countdown)
        logger.info(
            "Deferring access list sync by %s s (ESI downtime 11:00–11:15 UTC)",
            countdown,
        )
        return

    result = sync_executor_access_lists()
    if result.get("success"):
        logger.info(
            "Synced executor access lists: listed=%s synced=%s removed=%s",
            result.get("listed"),
            result.get("synced"),
            result.get("removed"),
        )
    else:
        logger.warning(
            "Executor access list sync failed: %s",
            result.get("error"),
        )
    return result
