from django.db.models import signals
from django.dispatch import receiver

from fleets.models import EveFleet
from fleets.tasks import update_fleet_schedule


@receiver(
    signals.post_save,
    sender=EveFleet,
    dispatch_uid="update_fleet_schedule_on_save",
)
def update_fleet_schedule_on_save(sender, instance, created, **kwargs):
    update_fleet_schedule()


@receiver(
    signals.post_delete,
    sender=EveFleet,
    dispatch_uid="update_fleet_schedule_on_delete",
)
def update_fleet_schedule_on_delete(sender, instance, **kwargs):
    update_fleet_schedule()
