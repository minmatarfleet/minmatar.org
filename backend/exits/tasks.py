import logging

from django.utils import timezone

from app.celery import app
from exits.helpers.alerts import send_alert
from exits.helpers.departures import confirm_due

logger = logging.getLogger(__name__)


@app.task(exclusive=15 * 60)
def confirm_departures():
    """Confirm departures whose 48-hour grace period has passed."""
    confirmed = confirm_due(timezone.now())
    logger.info("Confirmed %d departures", confirmed)
    return confirmed


@app.task
def alert_application(application_id: int):
    """Tell recruiters an applicant has alliance history, once (#3198)."""
    return send_alert(application_id)
