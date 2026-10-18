"""
The one place that signs and reads user JWTs.

Every login path (Discord, EVE SSO for mobile, the local fake login) and
the shared test helpers build their tokens here, so the signing key,
algorithm and claims live in one module. Tokens carry no ``exp`` claim
today: read docs/auth/authentication.md ("Tokens") before adding one,
because clients sign out when a token stops working.
"""

import jwt
from django.conf import settings
from django.utils import timezone

JWT_ALGORITHM = "HS256"


def encode_jwt(payload: dict) -> str:
    """Sign a payload with the site key. Claim order is kept as given."""
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_user_jwt(token: str) -> dict:
    """Verify the signature and return the claims.

    Raises ``jwt.InvalidTokenError`` (or a subclass) for anything that is
    not a token we signed.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])


def issue_discord_user_jwt(
    request, django_user, discord_user_data: dict
) -> str:
    """Token for a Discord login (website and desktop app)."""
    payload = {
        "user_id": django_user.id,
        "username": discord_user_data["username"],
        "avatar": (
            f"https://cdn.discordapp.com/avatars/"
            f"{django_user.discord_user.id}/{django_user.discord_user.avatar}.png"
        ),
        "is_superuser": django_user.is_superuser,
        "sub": discord_user_data["username"],
        "iss": request.get_host(),
        "iat": timezone.now(),
    }
    return encode_jwt(payload)


def issue_eve_character_jwt(
    request, character_id: int, character_name: str, user=None
) -> str:
    """Token for an EVE SSO login (mobile app).

    Always names the character. Adds the site account only when that
    character is linked to one, so a character-only token has no user_id
    and is rejected by ``AuthBearer`` endpoints.
    """
    payload = {
        "character_id": character_id,
        "character_name": character_name,
        "avatar": (
            f"https://images.evetech.net/characters/"
            f"{character_id}/portrait?size=128"
        ),
        "sub": str(character_id),
        "iss": request.get_host(),
        "iat": timezone.now(),
    }
    if user is not None:
        payload.update(
            {
                "user_id": user.id,
                "username": user.username,
                "is_superuser": user.is_superuser,
                "sub": user.username,
            }
        )
    return encode_jwt(payload)


def issue_fake_login_jwt(request, django_user) -> str:
    """Token for FAKE_LOGIN_USER_ID logins (local development only)."""
    payload = {
        "user_id": django_user.id,
        "username": django_user.username,
        "is_superuser": django_user.is_superuser,
        "sub": django_user.username,
        "iss": request.get_host(),
        "iat": timezone.now(),
    }
    return encode_jwt(payload)
