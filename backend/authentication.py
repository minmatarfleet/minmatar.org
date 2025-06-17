import logging
from typing import Any, Optional

import jwt
from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.http import HttpRequest
from ninja.security import HttpBearer

logger = logging.getLogger("authentication")


class AuthBearer(HttpBearer):
    """Authentication class for Ninja API methods"""

    def authenticate(self, request, token):
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=["HS256"]
            )
            user = User.objects.get(id=payload["user_id"])
            request.user = user
            return user
        except Exception as e:
            print(e)
            return None


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
    encoded_jwt_token = jwt.encode(
        payload, settings.SECRET_KEY, algorithm="HS256"
    )

    print(
        f"User '{user_name}' (ID {uid}) created with token {encoded_jwt_token}"
    )

    return user
