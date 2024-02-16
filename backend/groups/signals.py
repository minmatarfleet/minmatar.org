import logging

from django.db.models import signals
from django.dispatch import receiver

from groups.models import GroupRequest

logger = logging.getLogger(__name__)


@receiver(
    signals.post_save,
    sender=GroupRequest,
    dispatch_uid="group_request_post_save",
)
def group_request_post_save(sender, instance, created, **kwargs):
    logger.info("Group request saved, updating user groups")
    if instance.approved:
        instance.user.groups.add(instance.group)
    elif instance.approved is False:
        instance.user.groups.remove(instance.group)
    else:
        pass  # do nothing if approved is None, pending
