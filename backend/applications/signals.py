import logging

from django.db.models import signals
from django.dispatch import receiver
from django.conf import settings

from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveCorporation

from discord.client import DiscordClient
from groups.models import EveCorporationGroup

from .models import EveCorporationApplication

logger = logging.getLogger(__name__)
discord = DiscordClient()

APPLICATION_CHANNEL_ID = settings.DISCORD_APPLICATION_CHANNEL_ID


def _recruiter_corporation_group(corporation):
    """Return the 'recruiter' EveCorporationGroup for this corporation, if any."""
    return EveCorporationGroup.objects.filter(
        corporation=corporation,
        group_type=EveCorporationGroup.GROUP_TYPE_RECRUITER,
    ).first()


@receiver(
    signals.post_save,
    sender=EveCorporationApplication,
    dispatch_uid="eve_corporation_application_post_save",
)
def eve_corporation_application_post_save(
    sender, instance, created, **kwargs
):  # noqa # pylint: disable=unused-argument
    """Create a forum thread when an application is created"""
    if instance.discord_thread_id is None:
        user = instance.user
        primary_character = user_primary_character(user)
        corporation = EveCorporation.objects.filter(
            corporation_id=instance.corporation_id
        ).first()
        corp_name = (
            corporation.name if corporation else str(instance.corporation_id)
        )
        message = ""
        message += f"<@{user.discord_user.id}>"
        if corporation:
            group = _recruiter_corporation_group(corporation)
            if group:
                discord_group = group.group.discord_group
                discord_group_id = discord_group.role_id
                message += f"<@&{discord_group_id}>"
        message += "\n\n"
        message += f"Main Character: {primary_character.character_name}\n"
        message += f"Applying to: {corp_name}\n"
        message += f"Description: {instance.description}\n"
        application_url = f"https://my.minmatar.org/alliance/corporations/application/{instance.corporation_id}/{instance.id}"
        message += f"{application_url}\n"
        response = discord.create_forum_thread(
            channel_id=APPLICATION_CHANNEL_ID,
            title=f"{primary_character.character_name} - {corp_name}",
            message=message,
        )
        instance.discord_thread_id = int(response.json()["id"])
        instance.save()

    if instance.status == "accepted":
        message = ":tada: Your application has been accepted!\n"
        message += "- Read our [alliance values](https://wiki.minmatar.org/en/alliance/Minmatar_Fl33t_Tenets)\n"
        message += "- Apply in-game\n- Follow these [onboarding steps](https://wiki.minmatar.org/en/alliance/Onboarding)\n"
        message += "- Familiarize yourself with our [guides, values, and more](https://wiki.minmatar.org/)\n"
        message += "- [We are Minmatar (FL33T Alliance)](https://www.youtube.com/watch?v=JMddiOzaDsA)"
        discord.create_message(
            channel_id=instance.discord_thread_id, message=message
        )
        discord.close_thread(channel_id=instance.discord_thread_id)

    if instance.status == "rejected":
        message = ":bangbang: Your application has been rejected, please contact your recruiter for more information"
        discord.create_message(
            channel_id=instance.discord_thread_id, message=message
        )
        discord.close_thread(channel_id=instance.discord_thread_id)


@receiver(
    signals.pre_delete,
    sender=EveCorporationApplication,
    dispatch_uid="eve_corporation_application_pre_delete",
)
def eve_corporation_application_pre_delete(
    sender, instance, **kwargs
):  # noqa # pylint: disable=unused-argument
    """Close the forum thread if one exists"""
    try:
        if instance.discord_thread_id:
            message = ":bangbang: This application has been deleted"
            discord.create_message(
                channel_id=instance.discord_thread_id, message=message
            )
            discord.close_thread(channel_id=instance.discord_thread_id)
    except Exception as e:
        logger.error("Error closing discord thread: %s", e)
