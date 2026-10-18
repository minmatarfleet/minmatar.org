"""Shared helpers for backend tests.

Import these instead of re-implementing them per test module, so a change
to how the site signs its tokens is made once.
"""

from users.jwt_auth import encode_jwt


def make_token(user) -> str:
    """A bearer JWT for user, signed the way the site signs its own."""
    return encode_jwt({"user_id": user.pk})


def auth_headers(user) -> dict:
    """Django test client kwargs that authenticate as user."""
    return {"HTTP_AUTHORIZATION": f"Bearer {make_token(user)}"}
