import django
from django.contrib.auth.models import User
from esi.models import Token
from eveonline.models import EveCharacter
from eveonline.helpers.characters import set_primary_character

from app.testing import make_token


class TestCase(django.test.TestCase):
    """Base TestCase for the api.minmatar.org site"""

    def setUp(self):
        self.user = User.objects.create(username="test")
        self.token = make_token(self.user)

    def make_superuser(self):
        self.user.is_superuser = True
        self.user.save()

    def setup_character(self):
        """Create an EveCharacter and make it primary"""
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
