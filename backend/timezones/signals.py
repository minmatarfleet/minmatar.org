from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from eveonline.models import EvePlayer
from timezones.models import PilotTimezone


@receiver(
    post_save, sender=EvePlayer, dispatch_uid="timezones_declared_changed"
)
def reassess_on_declared_change(
    sender, instance, **kwargs
):  # pylint: disable=unused-argument
    """A new declared prime time takes effect now, not at the next run."""
    if not instance.user_id:
        return
    stored = (
        PilotTimezone.objects.filter(user_id=instance.user_id)
        .values_list("declared_prime_time", flat=True)
        .first()
    )
    if stored == instance.prime_time:
        return  # unchanged, or nothing declared and never assessed
    from timezones.tasks import (  # pylint: disable=import-outside-toplevel
        assess_user_timezone,
    )

    user_id = instance.user_id
    transaction.on_commit(lambda: assess_user_timezone.delay(user_id))
