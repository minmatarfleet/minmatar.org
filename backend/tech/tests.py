from django.db.models import signals
from django.test import Client
from django.contrib.auth.models import User

from esi.models import Token
from app.test import TestCase
from eveonline.models import EveCharacter, EvePrimaryCharacter

BASE_URL = "/api/tech"


class TechRoutesTestCase(TestCase):
    """Test cases for the tech router."""

    def setUp(self):
        # disconnect signals
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_private_data",
        )

        # create test client
        self.client = Client()

        super().setUp()

    def test_get_character(self):
        self.make_superuser()

        user = User.objects.first()
        token = Token.objects.create(
            user=user,
            character_id=123456,
        )
        char = EveCharacter.objects.create(
            character_id=token.character_id,
            character_name="Test Char",
            token=token,
        )
        EvePrimaryCharacter.objects.create(
            character=char,
            user=user,
        )

        response = self.client.get(
            f"{BASE_URL}/no_user_char",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
