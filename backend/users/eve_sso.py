"""EVE Online SSO helpers for mobile login via django-esi."""

import logging

from esi.models import Token

from app.errors import create_error_id
from eveonline.models import EveCharacter
from users.jwt_auth import issue_eve_character_jwt

logger = logging.getLogger(__name__)

EVE_LOGIN_SCOPES = "publicData"

OWNER_CHANGED = "CHARACTER_OWNER_CHANGED"
OWNER_NOT_VERIFIED = "CHARACTER_NOT_VERIFIED"


class CharacterOwnerNotVerified(Exception):
    """EVE login can't be tied to the site user who linked the character."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def verify_character_owner(character: EveCharacter, esi_token: Token) -> None:
    """Require the SSO owner hash to match the character's linked token.

    The linked token is the one the site user added through the
    Discord-authenticated add-character flow, so its owner hash is the EVE
    account that user proved. A character with no linked token or no
    stored hash is refused rather than trusted on first use: re-adding the
    character while logged in with Discord records a fresh hash.
    """
    linked = character.token
    stored_hash = linked.character_owner_hash if linked else ""
    if not stored_hash:
        raise CharacterOwnerNotVerified(OWNER_NOT_VERIFIED)
    if stored_hash != esi_token.character_owner_hash:
        raise CharacterOwnerNotVerified(OWNER_CHANGED)


def issue_mobile_jwt(request, esi_token: Token) -> str:
    """Issue a JWT from an ESI token. Includes user_id when the character is linked."""
    character = (
        EveCharacter.objects.filter(character_id=esi_token.character_id)
        .select_related("user", "token")
        .first()
    )
    if character and character.user_id:
        verify_character_owner(character, esi_token)

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
