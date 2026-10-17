import logging

from django.db.models import signals
from django.dispatch import receiver

from fleets.models import EveFleet
from fleets.tasks import queue_fleet_schedule_refresh

logger = logging.getLogger(__name__)


@receiver(
    signals.post_save,
    sender=EveFleet,
    dispatch_uid="update_fleet_schedule_on_save",
)
def update_fleet_schedule_on_save(sender, instance, created, **kwargs):
    if instance.audience and not instance.audience.add_to_schedule:
        return
    queue_fleet_schedule_refresh()


@receiver(signals.post_delete, sender=EveFleet)
def update_fleet_schedule_on_delete(sender, instance, **kwargs):
    queue_fleet_schedule_refresh()
