"""Auth helpers for buyback hangar sales."""

from app.errors import ErrorResponse
from buyback.models import EveBuybackSettings
from eveonline.helpers.characters import user_characters
from eveonline.models import EveCharacter
from industry.endpoints.planner.auth_helpers import auth_required_for_character


def is_buyback_coordinator(user) -> bool:
    if user is None or not getattr(user, "pk", None):
        return False
    return EveBuybackSettings.load().coordinators.filter(pk=user.pk).exists()


def can_manage_stock_sales(user) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return user.is_staff or is_buyback_coordinator(user)


def character_for_refine(request, character_id: int | None):
    """Load a refining character owned by the user, or an HTTP error tuple."""
    if character_id is None:
        return None, None
    auth_error = auth_required_for_character(request, character_id)
    if auth_error is not None:
        return None, auth_error
    allowed = {
        character.character_id for character in user_characters(request.user)
    }
    if character_id not in allowed:
        return None, (
            403,
            ErrorResponse(detail="Character not linked to your account."),
        )
    character = EveCharacter.objects.filter(character_id=character_id).first()
    if character is None:
        return None, (
            400,
            ErrorResponse(detail=f"Unknown character_id {character_id}"),
        )
    return character, None
