import jwt
from django.conf import settings
from django.contrib.auth.models import User
from ninja.security import HttpBearer


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


class UnauthorizedError(Exception):
    pass


def make_test_user(uid: int, user_name: str, is_super: bool):
    """Adds a test user to the database and displays a JWT token for it."""

    user = User(id=uid, username=user_name, is_superuser=is_super)
    user.save()
    print(f"User {uid} saved to database")

    payload = {
        "user_id": uid,
        "username": user_name,
        "is_superuser": is_super,
    }
    encoded_jwt_token = jwt.encode(
        payload, settings.SECRET_KEY, algorithm="HS256"
    )

    print(f"JWT bearer token: {encoded_jwt_token}")
