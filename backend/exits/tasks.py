import logging

from django.utils import timezone

from app.celery import app
from exits.helpers.departures import confirm_due

logger = logging.getLogger(__name__)


@app.task(exclusive=15 * 60)
def confirm_departures():
    """Confirm departures whose 48-hour grace period has passed."""
    confirmed = confirm_due(timezone.now())
    logger.info("Confirmed %d departures", confirmed)
    return confirmed
