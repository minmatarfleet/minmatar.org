import logging

from django.db.models import signals
from django.dispatch import receiver

from groups.models import GroupRequest, Sig, SigRequest, Team, TeamRequest

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


@receiver(
    signals.post_save,
    sender=SigRequest,
    dispatch_uid="sig_request_post_save",
)
def sig_request_post_save(sender, instance, created, **kwargs):
    logger.info("Sig request saved, updating user sigs")
    if instance.approved:
        instance.user.groups.add(instance.sig.group)
    elif instance.approved is False:
        instance.user.groups.remove(instance.sig.group)
    else:
        pass


@receiver(
    signals.post_save,
    sender=TeamRequest,
    dispatch_uid="team_request_post_save",
)
def team_request_post_save(sender, instance, created, **kwargs):
    logger.info("Team request saved, updating user teams")
    if instance.approved:
        instance.user.groups.add(instance.team.group)
    elif instance.approved is False:
        instance.user.groups.remove(instance.team.group)
    else:
        pass


@receiver(
    signals.m2m_changed,
    sender=Sig.members.through,
    dispatch_uid="sig_members_changed",
)
def sig_members_changed(
    sender, instance, action, reverse, model, pk_set, **kwargs
):
    logger.info("Sig members changed, updating user sigs")
    if action == "post_add":
        for user_id in pk_set:
            user = model.objects.get(pk=user_id)
            user.groups.add(instance.group)
    elif action == "post_remove":
        for user_id in pk_set:
            user = model.objects.get(pk=user_id)
            user.groups.remove(instance.group)
    else:
        pass


@receiver(
    signals.m2m_changed,
    sender=Team.members.through,
    dispatch_uid="team_members_changed",
)
def team_members_changed(
    sender, instance, action, reverse, model, pk_set, **kwargs
):
    logger.info("Team members changed, updating user teams")
    if action == "post_add":
        for user_id in pk_set:
            user = model.objects.get(pk=user_id)
            user.groups.add(instance.group)
    elif action == "post_remove":
        for user_id in pk_set:
            user = model.objects.get(pk=user_id)
            user.groups.remove(instance.group)
    else:
        pass
