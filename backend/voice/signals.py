"""Republish voice records when the data behind them changes.

Everything here is cheap when nobody uses voice: work is only queued for
pilots with a ``VoiceIdentity`` or fleets holding a branch.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from campaigns.models import CampaignParty
from discord.outbox import on_commit_enqueue
from eveonline.models import EveCharacter, EvePlayer
from fleets.models import (
    EveFleetInvite,
    EveFleetRoleVolunteer,
    EveFleetShipVolunteer,
)
from groups.models import UserAffiliation, UserCommunityStatus
from tribes.models import TribeGroupMembership
from voice.models import VoiceBan, VoiceChannelLease, VoiceIdentity
from voice.tasks import (
    publish_all_identities,
    publish_character_task,
    publish_user_characters,
    sync_fleet_task,
)


def _user_has_identity(user_id) -> bool:
    if not user_id:
        return False
    return VoiceIdentity.objects.filter(
        character_id__in=EveCharacter.objects.filter(user_id=user_id).values(
            "character_id"
        )
    ).exists()


def _republish_user(user_id):
    if _user_has_identity(user_id):

        on_commit_enqueue(
            publish_user_characters,
            (user_id,),
            context=f"voice user {user_id}",
        )


# EvePlayer: a new main is the only character that may connect.
@receiver([post_save, post_delete], sender=EvePlayer)
@receiver([post_save, post_delete], sender=TribeGroupMembership)
@receiver([post_save, post_delete], sender=UserAffiliation)
@receiver([post_save, post_delete], sender=UserCommunityStatus)
def user_access_changed(
    sender, instance, **kwargs
):  # pylint: disable=unused-argument
    _republish_user(instance.user_id)


@receiver([post_save, post_delete], sender=EveFleetRoleVolunteer)
@receiver([post_save, post_delete], sender=EveFleetShipVolunteer)
@receiver([post_save, post_delete], sender=EveFleetInvite)
def fleet_signup_changed(
    sender, instance, **kwargs
):  # pylint: disable=unused-argument
    fleet_id = instance.eve_fleet_id
    if VoiceChannelLease.active().filter(fleet_id=fleet_id).exists():

        on_commit_enqueue(
            sync_fleet_task, (fleet_id,), context=f"voice fleet {fleet_id}"
        )


@receiver([post_save, post_delete], sender=CampaignParty)
def campaign_party_changed(
    sender, instance, **kwargs
):  # pylint: disable=unused-argument
    if (
        VoiceChannelLease.active()
        .filter(fleet__campaign_id=instance.campaign_id)
        .exists()
    ):

        on_commit_enqueue(
            publish_all_identities, (), context="voice campaign allies"
        )


@receiver([post_save, post_delete], sender=VoiceBan)
def ban_changed(sender, instance, **kwargs):  # pylint: disable=unused-argument
    if VoiceIdentity.objects.filter(
        character_id=instance.character_id
    ).exists():

        on_commit_enqueue(
            publish_character_task,
            (instance.character_id,),
            context=f"voice ban {instance.character_id}",
        )
