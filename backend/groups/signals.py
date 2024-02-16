from django.db.models import signals
from django.dispatch import receiver

from groups.models import GroupRequest


@receiver(
    signals.post_save,
    sender=GroupRequest,
    dispatch_uid="group_request_post_save",
)
def group_request_post_save(sender, instance, created, **kwargs):
    if instance.approved:
        instance.group.user_set.add(instance.user)
    elif instance.approved is False:
        instance.group.user_set.remove(instance.user)
    else:
        pass  # do nothing if approved is None, pending
