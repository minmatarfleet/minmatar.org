import json
import logging

from django.conf import settings
from django.db.models import signals
from django.dispatch import receiver
from django.urls import reverse
from esi.clients import EsiClientProvider
from esi.models import Token

from discord.client import DiscordClient

from .models import EveCharacter, EveCorporation, EveCorporationApplication

logger = logging.getLogger(__name__)
discord = DiscordClient()
esi = EsiClientProvider()


@receiver(
    signals.post_save,
    sender=EveCharacter,
    dispatch_uid="populate_eve_character_public_data",
)
def populate_eve_character_public_data(sender, instance, created, **kwargs):
    logger.info("Populating name for character %s", instance.character_id)
    esi_character = esi.client.Character.get_characters_character_id(
        character_id=instance.character_id
    ).results()
    logger.debug("Setting character name to %s", esi_character["name"])
    instance.character_name = esi_character["name"]
    logger.debug("Setting corporation to %s", esi_character["corporation_id"])
    if EveCorporation.objects.filter(
        corporation_id=esi_character["corporation_id"]
    ).exists():
        instance.corporation = EveCorporation.objects.get(
            corporation_id=esi_character["corporation_id"]
        )
    else:
        corporation = EveCorporation.objects.create(
            corporation_id=esi_character["corporation_id"]
        )
        instance.corporation = corporation
    instance.save()


@receiver(
    signals.post_save,
    sender=EveCharacter,
    dispatch_uid="populate_eve_character_private_data",
)
def populate_eve_character_private_data(sender, instance, created, **kwargs):
    """Populate skills for a character"""
    if not instance.tokens.exists():
        return

    # populate skills
    logger.debug("Fetching skills for %s", instance.character_name)
    required_scopes = ["esi-skills.read_skills.v1"]
    token = Token.objects.filter(
        character_id=instance.character_id,
        scopes__name__in=required_scopes,
    ).first()
    if token:
        response = esi.client.Skills.get_characters_character_id_skills(
            character_id=instance.character_id,
            token=token.valid_access_token(),
        ).results()
        instance.skills_json = json.dumps(response)

    else:
        logger.warning(
            "Failed to populate skills, no token with required scopes for %s",
            instance.character_name,
        )

    instance.save()


@receiver(signals.post_save, sender=Token)
def token_post_save(
    sender, instance, created, **kwargs
):  # pylint: disable=unused-argument
    """Create / update a character when a token is created"""
    logger.info("Token saved, creating / updating character")
    character, _ = EveCharacter.objects.get_or_create(
        character_id=instance.character_id
    )
    character.save()


@receiver(signals.post_save, sender=EveCorporationApplication)
def eve_corporation_application_post_save(
    sender, instance, created, **kwargs
):  # noqa # pylint: disable=unused-argument
    """Create a forum thread when an application is created"""
    if instance.discord_thread_id is None:
        user = instance.user
        primary_character = EveCharacter.objects.get(
            character_id=user.eve_primary_token.token.character_id
        )
        message = ""
        message += f"<@{user.discord_user.id}>"
        message += "\n\n"
        message += f"Main Character: {primary_character.character_name}\n"
        message += f"Applying to: {instance.corporation.name}\n"
        message += f"Description: {instance.description}\n"
        application_url = settings.SITE_URL + reverse(
            "eveonline-corporations-applications-view",
            args=[instance.application.pk],
        )
        message += f"{application_url}\n"
        response = discord.create_forum_thread(
            channel_id=1097522187952467989,
            title=f"{primary_character.character_name} - {instance.corporation.name}",
            message=message,
        )
        instance.discord_thread_id = int(response.json()["id"])
        instance.save()

    if instance.status == "accepted":
        message = ":tada: Your application has been accepted! Please apply in-game and ask your recruiter for next steps."
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
