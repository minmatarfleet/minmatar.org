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
