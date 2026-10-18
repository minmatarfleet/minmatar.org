"""EVE Online SSO helpers for mobile login via django-esi."""

import logging

from esi.models import Token

from app.errors import create_error_id
from eveonline.models import EveCharacter
from users.jwt_auth import issue_eve_character_jwt

logger = logging.getLogger(__name__)

EVE_LOGIN_SCOPES = "publicData"


def issue_mobile_jwt(request, esi_token: Token) -> str:
    """Issue a JWT from an ESI token. Includes user_id when the character is linked."""
    character = (
        EveCharacter.objects.filter(character_id=esi_token.character_id)
        .select_related("user")
        .first()
    )

    user = None
    if character and character.user_id:
        user = character.user
        if esi_token.user_id != user.id:
            esi_token.user = user
            esi_token.save(update_fields=["user"])

    return issue_eve_character_jwt(
        request,
        esi_token.character_id,
        esi_token.character_name,
        user=user,
    )


def eve_login_error_redirect(redirect_url: str, code: str) -> str:
    error_id = create_error_id()
    logger.warning("EVE login failed: %s (%s)", code, error_id)
    return f"{redirect_url}?error={code}&id={error_id}"
