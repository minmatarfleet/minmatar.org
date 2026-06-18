"""Shared JWT helpers for user authentication."""

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone


def issue_discord_user_jwt(
    request, django_user, discord_user_data: dict
) -> str:
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
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_user_jwt(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])


def user_from_jwt_payload(payload: dict) -> User:
    return User.objects.get(id=payload["user_id"])
