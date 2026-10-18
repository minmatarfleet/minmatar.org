"""Shared helpers for backend tests.

Import these instead of re-implementing them per test module, so a change
to how the site signs its tokens is made once.
"""

import jwt
from django.conf import settings


def make_token(user) -> str:
    """A bearer JWT for user, signed the way the site signs its own."""
    return jwt.encode(
        {"user_id": user.pk}, settings.SECRET_KEY, algorithm="HS256"
    )


def auth_headers(user) -> dict:
    """Django test client kwargs that authenticate as user."""
    return {"HTTP_AUTHORIZATION": f"Bearer {make_token(user)}"}
