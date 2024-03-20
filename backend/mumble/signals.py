import logging

from django.db.models import signals
from django.dispatch import receiver
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)

@receiver(
    signals.post_save,
    sender=User,
    dispatch_uid="create_mumble_access",
)
def user_post_save(sender, instance, created, **kwargs):
    logger.info("User saved, creating mumble access")
    if created:
        from .models import MumbleAccess
        MumbleAccess.objects.create_mumble_access(instance)
    else:
        pass
