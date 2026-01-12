import logging

from django.db.models import signals
from django.dispatch import receiver

from esi.models import Token

from discord.client import DiscordClient
from eveonline.tasks import update_character_assets, update_character_skills
from eveonline.client import EsiClient, esi_public
from .models import (
    EveAlliance,
    EveCharacter,
    EveCorporation,
)

logger = logging.getLogger(__name__)
discord = DiscordClient()


@receiver(
    signals.post_save,
    sender=EveCharacter,
    dispatch_uid="populate_eve_character_public_data",
)
def populate_eve_character_public_data(sender, instance, created, **kwargs):
    if created:
        logger.debug("Populating name for character %s", instance.character_id)
        response = esi_public().get_character_public_data(
            instance.character_id
        )
        if not response.success():
            logger.error(
                "Error %d fetching public character data %d",
                response.response_code,
                instance.character_id,
            )
            return
        esi_character = response.data

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
        if not instance.token:
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


@receiver(
    signals.post_save,
    sender=EveAlliance,
    dispatch_uid="eve_alliance_post_save",
)
def eve_alliance_post_save(sender, instance, created, **kwargs):
    if created:
        logger.info("Post create of alliance %s", instance.alliance_id)
        # esi_alliance = esi.client.Alliance.get_alliances_alliance_id(
        #     alliance_id=instance.alliance_id
        # ).results()
        esi_response = EsiClient(None).get_alliance(instance.alliance_id)
        if not esi_response.success():
            logger.warning(
                "ESI error %d getting details of alliance %d",
                esi_response.response_code,
                instance.alliance_id,
            )
            return
        esi_alliance = esi_response.results()
        logger.debug("ESI alliance data: %s", esi_alliance)
        # public info
        logger.debug("Setting name to %s", esi_alliance["name"])
        instance.name = esi_alliance["name"]
        logger.debug("Setting ticker to %s", esi_alliance["ticker"])
        instance.ticker = esi_alliance["ticker"]
        if (
            "faction_id" in esi_alliance
            and esi_alliance["faction_id"] is not None
        ):
            logger.debug("Setting faction to %s", esi_alliance["faction_id"])
            instance.faction = EsiClient(None).get_faction(
                esi_alliance["faction_id"]
            )
        instance.save()


@receiver(
    signals.post_save,
    sender=Token,
    dispatch_uid="log_esi_token_creation",
)
def log_esi_token_creation(sender, instance, created, **kwargs):
    if created:
        logger.debug(
            "ESI token created for user %s, %s",
            instance.user if hasattr(instance, "user") else "*unknown*",
            instance.pk if hasattr(instance, "pk") else "*unknown*",
        )
