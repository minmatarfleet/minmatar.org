import django
import jwt
from django.conf import settings
from django.contrib.auth.models import User


class TestCase(django.test.TestCase):
    def setUp(self):
        self.user = User.objects.create(username="test")
        payload = {"user_id": self.user.id}
        encoded_jwt_token = jwt.encode(
            payload, settings.SECRET_KEY, algorithm="HS256"
        )
        self.token = encoded_jwt_token
