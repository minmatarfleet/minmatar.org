"""
Publish fleet refits and custom fits to the fleet commander's in-game saved
fittings via ESI, and remove them again when the fleet closes.

Saved fittings are named ``MM#<fleet id> <label>`` and carry a description
that names the fleet, so leftovers are easy to spot in the fitting window.
"""

import logging

from django.contrib.auth.models import User
from esi.models import Token

from eveonline.client import EsiClient
from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveCharacter
from eveonline.scopes import TokenType
from fleets.helpers.eft_items import eft_to_esi_fitting

logger = logging.getLogger(__name__)

FITTINGS_SCOPE = "esi-fittings.write_fittings.v1"
FITTINGS_TOKEN_TYPE = TokenType.FLEET_COMMANDER.value
ESI_FITTING_NAME_MAX = 50
ESI_FITTING_DESCRIPTION_MAX = 500


def fitting_publisher(user: User) -> EveCharacter | None:
    """
    The user's character whose ESI token can write fittings (primary first).
    None when no character has the scope yet.
    """
    if not user:
        return None
    characters = list(
        EveCharacter.objects.filter(user=user)
        .exclude(esi_suspended=True)
        .order_by("character_name")
    )
    if not characters:
        return None
    with_scope = set(
        Token.objects.filter(
            character_id__in=[c.character_id for c in characters],
            scopes__name=FITTINGS_SCOPE,
        ).values_list("character_id", flat=True)
    )
    primary = user_primary_character(user)
    if primary and primary.character_id in with_scope:
        return primary
    for character in characters:
        if character.character_id in with_scope:
            return character
    return None


def fitting_access(user: User) -> dict:
    """What the UI needs to guard refits / custom fits behind the scope."""
    prompt = user_primary_character(user) or (
        EveCharacter.objects.filter(user=user).order_by("id").first()
    )
    return {
        "can_publish": fitting_publisher(user) is not None,
        "scope": FITTINGS_SCOPE,
        "token_type": FITTINGS_TOKEN_TYPE,
        "character_id": prompt.character_id if prompt else None,
        "character_name": prompt.character_name if prompt else None,
    }


def missing_scope_detail() -> str:
    return (
        "Saving fits in-game needs the "
        f"{FITTINGS_SCOPE} scope on one of your characters. "
        "Add the Fleet Commander token and try again."
    )


def esi_fitting_name(fleet_id: int, label: str) -> str:
    name = f"MM#{fleet_id} {label}".strip()
    return name[:ESI_FITTING_NAME_MAX]


def esi_fitting_description(fleet_id: int, kind: str, detail: str) -> str:
    text = (
        f"minmatar.org fleet #{fleet_id} {kind}: {detail}. "
        "Created for the fleet MOTD and removed when the fleet ends."
    )
    return text[:ESI_FITTING_DESCRIPTION_MAX]


def publish_fitting(
    publisher: EveCharacter,
    fleet_id: int,
    label: str,
    kind: str,
    detail: str,
    eft_format: str,
) -> tuple[int | None, str | None]:
    """
    Save ``eft_format`` under the publisher's character.
    Returns (esi_fitting_id, error).
    """
    ship_type_id, items = eft_to_esi_fitting(eft_format)
    if not ship_type_id:
        return None, "Could not resolve the hull for the in-game fitting"
    body = {
        "name": esi_fitting_name(fleet_id, label),
        "description": esi_fitting_description(fleet_id, kind, detail),
        "ship_type_id": ship_type_id,
        "items": items,
    }
    response = EsiClient(publisher.character_id).create_character_fitting(body)
    if not response.success():
        logger.warning(
            "ESI fitting create failed for fleet %s (%s): %s %s",
            fleet_id,
            publisher.character_id,
            response.response_code,
            response.response,
        )
        return None, f"ESI refused the fitting ({response.response_code})"
    fitting_id = (response.data or {}).get("fitting_id")
    return fitting_id, None


def publish_and_store(obj, publisher, fleet_id, label, kind, detail, eft):
    """publish_fitting + persist esi_fitting_id / esi_character_id on obj."""
    fitting_id, error = publish_fitting(
        publisher, fleet_id, label, kind, detail, eft
    )
    if fitting_id:
        obj.esi_fitting_id = fitting_id
        obj.esi_character_id = publisher.character_id
        obj.save(update_fields=["esi_fitting_id", "esi_character_id"])
    return error


def unpublish(obj) -> bool:
    """
    Delete the in-game fitting recorded on ``obj`` (EveFleetFitting or
    EveFleetFittingRefit). Clears the ids on success or when ESI no longer
    knows the fitting. Never raises.
    """
    if not obj.esi_fitting_id or not obj.esi_character_id:
        return True
    try:
        response = EsiClient(obj.esi_character_id).delete_character_fitting(
            obj.esi_fitting_id
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.warning("ESI fitting delete raised: %s", e)
        return False
    if not response.success() and response.response_code != 404:
        logger.warning(
            "ESI fitting delete failed (%s/%s): %s",
            obj.esi_character_id,
            obj.esi_fitting_id,
            response.response_code,
        )
        return False
    obj.esi_fitting_id = None
    obj.esi_character_id = None
    if obj.pk:
        obj.save(update_fields=["esi_fitting_id", "esi_character_id"])
    return True


def cleanup_fleet_esi_fittings(fleet) -> int:
    """Remove every in-game fitting created for the fleet; returns failures."""
    from fleets.models import (  # pylint: disable=import-outside-toplevel
        EveFleetFitting,
        EveFleetFittingRefit,
    )

    failures = 0
    for model in (EveFleetFitting, EveFleetFittingRefit):
        for obj in model.objects.filter(
            eve_fleet=fleet, esi_fitting_id__isnull=False
        ):
            if not unpublish(obj):
                failures += 1
    return failures
