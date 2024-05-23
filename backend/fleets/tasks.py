import logging

from django.utils import timezone

from app.celery import app
from fleets.models import EveFleetInstance, EveStandingFleet

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


@app.task()
def update_standing_fleet_instances():
    for standing_fleet in EveStandingFleet.objects.filter(end_time=None):
        logger.info("Updating standing fleet instance %s", standing_fleet.id)
        try:
            standing_fleet.update_fleet_members()
        except Exception as e:
            logger.info(
                "An error occurred while updating standing fleet instance %s: %s",
                standing_fleet.id,
                e,
            )
            logger.info("Assuming fleet is closed")
            standing_fleet.end_time = timezone.now()
            standing_fleet.save()
