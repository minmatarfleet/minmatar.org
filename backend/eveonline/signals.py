import logging

from django.db.models import signals
from django.dispatch import receiver
from esi.clients import EsiClientProvider
from esi.models import Token
from eveuniverse.models import EveFaction

from discord.client import DiscordClient
from discord.helpers import DISCORD_PEOPLE_TEAM_CHANNEL_ID
from eveonline.tasks import update_character_assets, update_character_skills

from .models import (
    EveAlliance,
    EveCharacter,
    EveCharacterLog,
    EveCorporation,
    EvePrimaryCharacterChangeLog,
)

logger = logging.getLogger(__name__)
discord = DiscordClient()
esi = EsiClientProvider()


@receiver(
    signals.post_save,
    sender=EveCharacter,
    dispatch_uid="populate_eve_character_public_data",
)
def populate_eve_character_public_data(sender, instance, created, **kwargs):
    if created:
        logger.info("Populating name for character %s", instance.character_id)
        esi_character = esi.client.Character.get_characters_character_id(
            character_id=instance.character_id
        ).results()
        logger.debug("Setting character name to %s", esi_character["name"])
        instance.character_name = esi_character["name"]
        logger.debug(
            "Setting corporation to %s", esi_character["corporation_id"]
        )
        corporation, _ = EveCorporation.objects.get_or_create(
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
    if created:
        if not instance.tokens.exists():
            return

        # populate skills
        logger.debug("Fetching skills for %s", instance.character_name)
        update_character_skills.apply_async(
            args=[instance.character_id], countdown=30
        )

        # populate assets
        logger.debug("Fetching assets for %s", instance.character_name)
        update_character_assets.apply_async(
            args=[instance.character_id], countdown=30
        )

        instance.save()


@receiver(signals.post_save, sender=Token)
def token_post_save(
    sender, instance: Token, created, **kwargs
):  # pylint: disable=unused-argument
    """Create / update a character when a token is created"""
    logger.info("Token saved, creating / updating character")
    character, _ = EveCharacter.objects.get_or_create(
        character_id=instance.character_id
    )
    character.token = instance
    character.save()

    EveCharacterLog.objects.create(
        username=instance.user.username,
        character_name=character.character_name,
    )


@receiver(
    signals.post_save,
    sender=EveAlliance,
    dispatch_uid="eve_alliance_post_save",
)
def eve_alliance_post_save(sender, instance, created, **kwargs):
    if created:
        logger.info("Post create of alliance %s", instance.alliance_id)
        esi_alliance = esi.client.Alliance.get_alliances_alliance_id(
            alliance_id=instance.alliance_id
        ).results()
        logger.info("ESI alliance data: %s", esi_alliance)
        # public info
        logger.info("Setting name to %s", esi_alliance["name"])
        instance.name = esi_alliance["name"]
        logger.info("Setting ticker to %s", esi_alliance["ticker"])
        instance.ticker = esi_alliance["ticker"]
        if (
            "faction_id" in esi_alliance
            and esi_alliance["faction_id"] is not None
        ):
            logger.info("Setting faction to %s", esi_alliance["faction_id"])
            instance.faction = EveFaction.objects.get_or_create_esi(
                id=esi_alliance["faction_id"],
            )[0]
        instance.save()


@receiver(
    signals.post_save,
    sender=EvePrimaryCharacterChangeLog,
    dispatch_uid="notify_people_team_of_primary_character_change",
)
def notify_people_team_of_primary_character_change(
    sender, instance, created, **kwargs
):
    if created:
        discord.create_message(
            DISCORD_PEOPLE_TEAM_CHANNEL_ID,
            f"Primary character change for {instance.username} from {instance.previous_character_name} to {instance.new_character_name}",
        )
