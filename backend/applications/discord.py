"""Discord helpers for corporation applications."""

import logging

from django.conf import settings

from discord.client import DiscordClient
from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveCorporation
from groups.models import EveCorporationGroup

from .l3arn import application_discord_description

logger = logging.getLogger(__name__)
discord = DiscordClient()

APPLICATION_CHANNEL_ID = settings.DISCORD_APPLICATION_CHANNEL_ID


def recruiter_corporation_group(corporation):
    """Return the 'recruiter' EveCorporationGroup for this corporation, if any."""
    return EveCorporationGroup.objects.filter(
        corporation=corporation,
        group_type=EveCorporationGroup.GROUP_TYPE_RECRUITER,
    ).first()


def _recruiter_role_mention(corporation) -> str:
    if not corporation:
        return ""
    group = recruiter_corporation_group(corporation)
    if not group:
        return ""
    try:
        discord_group = group.group.discord_group
    except Exception:
        return ""
    if not discord_group or not discord_group.role_id:
        return ""
    return f"<@&{discord_group.role_id}>"


def application_url(application) -> str:
    return (
        "https://my.minmatar.org/alliance/corporations/application/"
        f"{application.corporation_id}/{application.id}"
    )


def application_thread_title(application, corporation=None) -> str:
    primary_character = user_primary_character(application.user)
    if corporation is None:
        corporation = EveCorporation.objects.filter(
            corporation_id=application.corporation_id
        ).first()
    corp_name = (
        corporation.name if corporation else str(application.corporation_id)
    )
    character_name = (
        primary_character.character_name
        if primary_character
        else application.user.username
    )
    return f"{character_name} - {corp_name}"


def application_starter_message(application, corporation=None) -> str:
    user = application.user
    primary_character = user_primary_character(user)
    if corporation is None:
        corporation = EveCorporation.objects.filter(
            corporation_id=application.corporation_id
        ).first()
    corp_name = (
        corporation.name if corporation else str(application.corporation_id)
    )
    character_name = (
        primary_character.character_name
        if primary_character
        else user.username
    )

    message = f"<@{user.discord_user.id}>"
    message += _recruiter_role_mention(corporation)
    message += "\n\n"
    message += f"Main Character: {character_name}\n"
    message += f"Applying to: {corp_name}\n"
    description = application_discord_description(application.description)
    message += f"Description: {description}\n"
    message += f"{application_url(application)}\n"
    return message


def create_application_thread(application) -> int:
    """Create the Discord forum thread for an application and return its id."""
    corporation = EveCorporation.objects.filter(
        corporation_id=application.corporation_id
    ).first()
    response = discord.create_forum_thread(
        channel_id=APPLICATION_CHANNEL_ID,
        title=application_thread_title(application, corporation),
        message=application_starter_message(application, corporation),
    )
    return int(response.json()["id"])


def notify_application_accepted(application) -> None:
    message = ":tada: Your application has been accepted!\n"
    message += "- Read our [alliance values](https://my.minmatar.org/alliance/values/)\n"
    message += "- Apply in-game\n- Follow these [onboarding steps](https://wiki.minmatar.org/en/alliance/Onboarding)\n"
    message += "- Familiarize yourself with our [Learning](https://my.minmatar.org/learning/)\n"
    message += "- [We are Minmatar (FL33T Alliance)](https://www.youtube.com/watch?v=JMddiOzaDsA)"
    discord.create_message(
        channel_id=application.discord_thread_id, message=message
    )
    discord.close_thread(channel_id=application.discord_thread_id)


def notify_application_rejected(application) -> None:
    message = (
        ":bangbang: Your application has been rejected, "
        "please contact your recruiter for more information"
    )
    discord.create_message(
        channel_id=application.discord_thread_id, message=message
    )
    discord.close_thread(channel_id=application.discord_thread_id)


def notify_application_deleted(application) -> None:
    message = ":bangbang: This application has been deleted"
    discord.create_message(
        channel_id=application.discord_thread_id, message=message
    )
    discord.close_thread(channel_id=application.discord_thread_id)


def notify_application_transferred(
    application,
    *,
    previous_corporation_id: int,
    transferred_by_username: str,
) -> None:
    """Rename the thread, refresh the starter post, and announce the transfer."""
    if not application.discord_thread_id:
        return

    previous_corporation = EveCorporation.objects.filter(
        corporation_id=previous_corporation_id
    ).first()
    new_corporation = EveCorporation.objects.filter(
        corporation_id=application.corporation_id
    ).first()
    previous_name = (
        previous_corporation.name
        if previous_corporation
        else str(previous_corporation_id)
    )
    new_name = (
        new_corporation.name
        if new_corporation
        else str(application.corporation_id)
    )

    try:
        discord.rename_thread(
            channel_id=application.discord_thread_id,
            name=application_thread_title(application, new_corporation),
        )
    except Exception as e:
        logger.error("Error renaming application discord thread: %s", e)

    # Forum starter message id matches the thread id.
    try:
        discord.update_message(
            channel_id=application.discord_thread_id,
            message_id=application.discord_thread_id,
            message=application_starter_message(application, new_corporation),
        )
    except Exception as e:
        logger.error(
            "Error updating application discord starter message: %s", e
        )

    message = (
        f":left_right_arrow: Application transferred from **{previous_name}** "
        f"to **{new_name}** by {transferred_by_username}\n"
    )
    recruiter_mention = _recruiter_role_mention(new_corporation)
    if recruiter_mention:
        message += f"{recruiter_mention}\n"
    message += application_url(application)

    try:
        discord.create_message(
            channel_id=application.discord_thread_id, message=message
        )
    except Exception as e:
        logger.error("Error notifying application transfer on discord: %s", e)
