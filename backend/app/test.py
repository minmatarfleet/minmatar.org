import django
import jwt
from django.conf import settings
from django.contrib.auth.models import User
from esi.models import Token
from eveonline.models import EveCharacter
from eveonline.helpers.characters import set_primary_character


class TestCase(django.test.TestCase):
    """Base TestCase for the api.minmatar.org site"""

    def setUp(self):
        self.user = User.objects.create(username="test")
        payload = {"user_id": self.user.id}
        encoded_jwt_token = jwt.encode(
            payload, settings.SECRET_KEY, algorithm="HS256"
        )
        self.token = encoded_jwt_token

    def make_superuser(self):
        self.user.is_superuser = True
        self.user.save()

    def setup_character(self):
        """Create an EveCharacter and EvePrimaryCharacter"""
        user = User.objects.first()
        token = Token.objects.create(
            user=user,
            character_id=123456,
        )
        char = EveCharacter.objects.create(
            character_id=token.character_id,
            character_name="Test Char",
            user=user,
            token=token,
        )
        set_primary_character(user, char)
