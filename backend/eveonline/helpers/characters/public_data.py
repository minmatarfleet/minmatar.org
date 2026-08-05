import logging

from django.utils import timezone
from esi.exceptions import ESIErrorLimitException

from eveonline.client import EsiResponse, esi_public, live_esi_allowed
from eveonline.helpers.characters.characters import orphan_character
from eveonline.models import EveCharacter

logger = logging.getLogger(__name__)

DELETED_CHARACTER_ERROR = "Character has been deleted"


def apply_character_public_data(
    character: EveCharacter, esi_character: dict
) -> bool:
    """Apply public ESI character fields to an in-memory EveCharacter."""
    updated = False

    name = esi_character.get("name")
    if name and character.character_name != name:
        character.character_name = name
        updated = True

    corporation_id = esi_character.get("corporation_id")
    if (
        corporation_id is not None
        and character.corporation_id != corporation_id
    ):
        character.corporation_id = corporation_id
        updated = True

    security_status = esi_character.get("security_status")
    if security_status is not None:
        security_status = float(security_status)
        if character.security_status != security_status:
            character.security_status = security_status
            updated = True

    return updated


def is_character_deleted_response(response: EsiResponse) -> bool:
    """True when ESI indicates the character ID no longer exists."""
    if response.response_code == 404:
        return True
    text = str(response.response or "")
    return DELETED_CHARACTER_ERROR in text


def is_esi_error_limited_response(response: EsiResponse) -> bool:
    """True when ESI error budget is exhausted (HTTP 420 / ESIErrorLimitException)."""
    if response.response_code == 420:
        return True
    return isinstance(response.response, ESIErrorLimitException)


def mark_character_esi_deleted(character: EveCharacter) -> None:
    """Flag a biomassed character and detach user/token so we stop ESI calls."""
    character.esi_deleted = True
    character.esi_deleted_at = timezone.now()
    character.save(update_fields=["esi_deleted", "esi_deleted_at"])
    orphan_character(character)
    logger.info(
        "Marked character %s (%s) as ESI-deleted",
        character.character_name,
        character.character_id,
    )


def update_character_public_data(character_id: int) -> bool:
    """Fetch public ESI data and persist name, corporation, and security status.

    Raises ESIErrorLimitException when ESI error budget is exhausted so bulk
    callers can abort the sweep instead of burning further errors.
    """
    character = EveCharacter.objects.get(character_id=character_id)
    if character.esi_deleted:
        return False
    if not live_esi_allowed():
        logger.info(
            "Skipping character public data ESI for %s during tests",
            character_id,
        )
        return False

    response = esi_public().get_character_public_data(character_id)
    if not response.success():
        if is_character_deleted_response(response):
            mark_character_esi_deleted(character)
            return False
        if is_esi_error_limited_response(response):
            if isinstance(response.response, ESIErrorLimitException):
                raise response.response
            raise ESIErrorLimitException()
        logger.warning(
            "ESI error %s fetching public data for character %s",
            response.response_code,
            character_id,
        )
        return False

    updated = apply_character_public_data(character, response.data)
    if updated:
        character.save()
        logger.info(
            "Updated public data for character %s (%s)",
            character.character_name,
            character_id,
        )
    return updated
