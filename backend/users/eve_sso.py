"""EVE Online SSO helpers for mobile login via django-esi."""

import logging

import jwt
from django.conf import settings
from django.utils import timezone
from esi.models import Token

from app.errors import create_error_id
from eveonline.models import EveCharacter

logger = logging.getLogger(__name__)

EVE_LOGIN_SCOPES = "publicData"


class EveSsoError(Exception):
    def __init__(self, code: str, message: str = ""):
        self.code = code
        self.message = message
        super().__init__(code)


def issue_mobile_jwt(request, esi_token: Token) -> str:
    """Issue a JWT from an ESI token. Includes user_id when the character is linked."""
    character = (
        EveCharacter.objects.filter(character_id=esi_token.character_id)
        .select_related("user")
        .first()
    )

    payload = {
        "character_id": esi_token.character_id,
        "character_name": esi_token.character_name,
        "avatar": (
            f"https://images.evetech.net/characters/"
            f"{esi_token.character_id}/portrait?size=128"
        ),
        "sub": str(esi_token.character_id),
        "iss": request.get_host(),
        "iat": timezone.now(),
    }

    if character and character.user_id:
        user = character.user
        payload.update(
            {
                "user_id": user.id,
                "username": user.username,
                "is_superuser": user.is_superuser,
                "sub": user.username,
            }
        )
        if esi_token.user_id != user.id:
            esi_token.user = user
            esi_token.save(update_fields=["user"])

    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def eve_login_error_redirect(redirect_url: str, code: str) -> str:
    error_id = create_error_id()
    logger.warning("EVE login failed: %s (%s)", code, error_id)
    return f"{redirect_url}?error={code}&id={error_id}"
