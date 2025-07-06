import logging

from django.contrib.auth.models import Group
from django.db.models import signals
from django.dispatch import receiver

from groups.models import Sig, SigRequest, Team, TeamRequest, UserAffiliation

logger = logging.getLogger(__name__)


@receiver(
    signals.pre_save,
    sender=SigRequest,
    dispatch_uid="sig_request_post_save",
)
def sig_request_post_save(sender, instance, **kwargs):
    logger.info("Sig request saved, updating user sigs")
    if instance.approved:
        instance.sig.members.add(instance.user)
        instance.user.groups.add(instance.sig.group)
    elif instance.approved is False:
        instance.sig.members.remove(instance.user)
        instance.user.groups.remove(instance.sig.group)
    else:
        pass


@receiver(
    signals.pre_save,
    sender=TeamRequest,
    dispatch_uid="team_request_post_save",
)
def team_request_post_save(sender, instance, **kwargs):
    logger.info("Team request saved, updating user teams")
    if instance.approved:
        instance.team.members.add(instance.user)
        instance.user.groups.add(instance.team.group)
    elif instance.approved is False:
        instance.team.members.remove(instance.user)
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
    sender=Team.directors.through,
    dispatch_uid="team_directors_changed",
)
def team_directors_changed(
    sender, instance, action, reverse, model, pk_set, **kwargs
):
    group, _ = Group.objects.get_or_create(name="Alliance Director")
    logger.info("Team directors changed (%s), updating user groups", action)
    if action == "pre_add":
        for user_id in pk_set:
            user = model.objects.get(pk=user_id)
            logger.info("Adding team director %s to group %s", user, group)
            user.groups.add(group)
    elif action == "pre_remove":
        for user_id in pk_set:
            user = model.objects.get(pk=user_id)
            logger.info("Removing team director %s from group %s", user, group)
            user.groups.remove(group)
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


@receiver(
    signals.pre_delete,
    sender=UserAffiliation,
    dispatch_uid="user_affiliation_pre_delete",
)
def user_affiliation_pre_delete(sender, instance, **kwargs):
    logger.info("User affiliation deleted, updating user groups")
    instance.user.groups.remove(instance.affiliation.group)


@receiver(
    signals.post_save,
    sender=UserAffiliation,
    dispatch_uid="user_affiliation_post_save",
)
def user_affiliation_post_save(sender, instance, created, **kwargs):
    logger.info("User affiliation saved, updating user groups")
    instance.user.groups.add(instance.affiliation.group)
