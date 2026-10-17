import logging
from typing import Any, Optional

import jwt
from django.contrib.auth.models import AnonymousUser, User
from django.core.cache import cache
from django.http import HttpRequest
from ninja.errors import HttpError
from ninja.security import HttpBearer

from users.jwt_auth import decode_user_jwt, encode_jwt

logger = logging.getLogger("authentication")

SERVICE_ACCOUNT_APP_LABEL = "users"
SERVICE_ACCOUNT_CODENAME = "service_account"
SERVICE_ACCOUNT_PERMISSION = (
    f"{SERVICE_ACCOUNT_APP_LABEL}.{SERVICE_ACCOUNT_CODENAME}"
)
STAFF_FALLBACK_LOG_SECONDS = 3600


class AuthBearer(HttpBearer):
    """Authentication class for Ninja API methods"""

    def authenticate(self, request, token):
        """The user a bearer token names, or None for a 401.

        Only a bad token or a missing user is a 401. Anything else, such
        as the database being down, raises and becomes a 500, so clients
        don't treat an outage as being signed out.
        """
        try:
            payload = decode_user_jwt(token)
        except jwt.InvalidTokenError as e:
            logger.debug("Bearer token rejected: %s", e)
            return None

        user_id = payload.get("user_id")
        if user_id is None:
            # e.g. a mobile EVE SSO token for a character with no account
            logger.debug("Bearer token has no user_id")
            return None

        try:
            user = User.objects.get(id=user_id)
        except (User.DoesNotExist, ValueError, TypeError):
            logger.debug("Bearer token for unknown user %s", user_id)
            return None

        request.user = user
        return user


def has_service_account_permission(user) -> bool:
    """True when the permission is granted to this user directly.

    Deliberately not ``user.has_perm``: that is always True for a
    superuser, and the point is to tell the bot apart from staff.
    """
    if not getattr(user, "is_authenticated", False) or not user.pk:
        return False
    return user.user_permissions.filter(
        content_type__app_label=SERVICE_ACCOUNT_APP_LABEL,
        codename=SERVICE_ACCOUNT_CODENAME,
    ).exists()


def _log_staff_fallback(user) -> None:
    """Shadow mode: note a staff user passing as the bot, once an hour."""
    key = f"service_account:staff_fallback:{user.pk}"
    try:
        first_this_hour = cache.add(key, 1, STAFF_FALLBACK_LOG_SECONDS)
    except Exception:  # pylint: disable=broad-except
        first_this_hour = True  # cache down: log rather than stay silent
    if first_this_hour:
        logger.warning(
            "Service-account check passed by staff fallback "
            "(user_id=%s, is_staff=%s, is_superuser=%s); grant %s to the "
            "bot's user before the fallback is removed",
            user.pk,
            user.is_staff,
            user.is_superuser,
            SERVICE_ACCOUNT_PERMISSION,
        )


def is_service_account(user) -> bool:
    """
    True when the caller is the Discord bot's API user.

    The bot is the user holding the ``users.service_account`` permission.
    Shadow mode: any staff or superuser still passes, as before, and is
    logged so the fallback can be dropped once only the bot shows up.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if has_service_account_permission(user):
        return True
    if getattr(user, "is_staff", False) or getattr(
        user, "is_superuser", False
    ):
        _log_staff_fallback(user)
        return True
    return False


def require_service_account(request) -> None:
    """Endpoints only the bot may call: any member token gets a 403."""
    if not is_service_account(getattr(request, "user", None)):
        raise HttpError(403, "Only the Discord bot may call this endpoint.")


class AuthOptional(AuthBearer):
    """Authentication class for Ninja API methods"""

    def __call__(self, request: HttpRequest) -> Optional[Any]:
        # Override this to return AnonymousUser if no auth token rather than failing auth.
        headers = request.headers
        auth_value = headers.get(self.header)
        if not auth_value:
            return AnonymousUser()
        parts = auth_value.split(" ")

        if parts[0].lower() != self.openapi_scheme:
            return None
        token = " ".join(parts[1:])
        return self.authenticate(request, token)


class UnauthorizedError(Exception):
    pass


def make_test_user(uid: int, user_name: str, is_super: bool):
    """Adds a test user to the database and displays a JWT token for it."""

    user = User(id=uid, username=user_name, is_superuser=is_super)
    user.save()

    payload = {
        "user_id": uid,
        "username": user_name,
        "is_superuser": is_super,
    }
    encoded_jwt_token = encode_jwt(payload)

    print(
        f"User '{user_name}' (ID {uid}) created with token {encoded_jwt_token}"
    )

    return user
