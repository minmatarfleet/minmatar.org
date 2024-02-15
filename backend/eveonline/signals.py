import json
import logging

from django.conf import settings
from django.db.models import signals
from django.dispatch import receiver
from django.urls import reverse
from esi.clients import EsiClientProvider
from esi.models import Token
from eveuniverse.models import EveFaction

from discord.client import DiscordClient

from .models import EveCharacter, EveCorporation, EveAlliance

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
    character.token = instance
    character.save()


@receiver(
    signals.post_save,
    sender=EveCorporation,
    dispatch_uid="eve_corporation_post_save",
)
def eve_corporation_post_save(sender, instance, created, **kwargs):
    if created:
        esi_corporation = esi.client.Corporation.get_corporations_corporation_id(
            corporation_id=instance.corporation_id
        ).results()
        instance.name = esi_corporation["name"]
        instance.ticker = esi_corporation["ticker"]
        instance.member_count = esi_corporation["member_count"]
        instance.ceo = EveCharacter.objects.get_or_create(
            character_id=esi_corporation["ceo_id"],
        )[0]
        instance.alliance = EveAlliance.objects.get_or_create(
            alliance_id=esi_corporation["alliance_id"],
        )[0]
        instance.faction = EveFaction.objects.get_or_create_esi(
            id=esi_corporation["faction_id"],
        )[0]

        if esi_corporation["alliance_id"] == 99011978:
            instance.type = "alliance"
        elif esi_corporation["alliance_id"] == 99012009:
            instance.type = "associate"
        elif esi_corporation["faction_id"] == 500002:
            instance.type = "militia"
        else:
            instance.type = "public"

        instance.save()
