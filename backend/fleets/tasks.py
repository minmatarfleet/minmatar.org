import logging

from django.utils import timezone

from app.celery import app
from fleets.models import EveFleetInstance

logger = logging.getLogger(__name__)


@app.task()
def update_fleet_instances():
    """
    Update fleet instances
    """
    for fleet_instance in EveFleetInstance.objects.filter(end_time=None):
        logger.info("Updating fleet instance %s", fleet_instance.id)
        try:
            fleet_instance.update_is_registered_status()
            fleet_instance.update_fleet_members()
        except Exception as e:
            logger.info(
                "An error occurred while updating fleet instance %s: %s",
                fleet_instance.id,
                e,
            )
            logger.info("Assuming fleet is closed")
            fleet_instance.end_time = timezone.now()
            fleet_instance.save()
