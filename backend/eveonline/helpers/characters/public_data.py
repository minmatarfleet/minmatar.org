import logging

from eveonline.client import esi_public
from eveonline.models import EveCharacter

logger = logging.getLogger(__name__)


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


def update_character_public_data(character_id: int) -> bool:
    """Fetch public ESI data and persist name, corporation, and security status."""
    character = EveCharacter.objects.get(character_id=character_id)
    response = esi_public().get_character_public_data(character_id)
    if not response.success():
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
