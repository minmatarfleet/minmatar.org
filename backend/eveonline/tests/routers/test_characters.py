from django.db.models import signals
from django.test import Client
from django.contrib.auth.models import User

from esi.models import Token
from app.test import TestCase
from eveonline.models import (
    EveCharacter,
    EvePrimaryCharacter,
    EvePrimaryCharacterChangeLog,
)
from eveonline.scopes import TokenType, token_type_str
from eveonline.helpers.characters import (
    user_primary_character,
    user_characters,
)

BASE_URL = "/api/eveonline/characters/"


class CharacterRouterTestCase(TestCase):
    """Test cases for the character router."""

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
        signals.post_save.disconnect(
            sender=EvePrimaryCharacterChangeLog,
            dispatch_uid="notify_people_team_of_primary_character_change",
        )

        # create test client
        self.client = Client()

        super().setUp()

    def make_superuser(self):
        self.user.is_superuser = True
        self.user.save()

    def make_character(
        self, user: User, character_id: int, name: str
    ) -> EveCharacter:
        """Creates an EveCharacter with an ESI token."""
        token = Token.objects.create(
            user=user,
            character_id=character_id,
        )
        return EveCharacter.objects.create(
            character_id=token.character_id,
            character_name=name,
            token=token,
        )

    def test_get_characters_success(self):
        response = self.client.get(
            BASE_URL, HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_get_characters_failure_unauthorized(self):
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, 401)

    def test_get_character_by_id_failure_not_found(self):
        response = self.client.get(
            f"{BASE_URL}123", HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 404)

    def test_get_character_by_id_failure_unauthorized(self):
        character = EveCharacter.objects.create(character_id=123)
        response = self.client.get(f"{BASE_URL}{character.character_id}")
        self.assertEqual(response.status_code, 401)

    def test_get_character_by_id(self):
        self.make_superuser()
        character = EveCharacter.objects.create(character_id=123)
        response = self.client.get(
            f"{BASE_URL}{character.character_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)

    def test_get_primary_character_none(self):
        self.make_superuser()
        character = EveCharacter.objects.create(character_id=123)
        response = self.client.get(
            f"{BASE_URL}primary?character_id={character.character_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 404)

    def test_token_type_str(self):
        self.assertEqual("", token_type_str(None))
        self.assertEqual("", token_type_str(""))
        self.assertEqual("Basic", token_type_str("Basic"))
        self.assertEqual("Basic", token_type_str(TokenType.BASIC))
        self.assertEqual("CEO", token_type_str(TokenType.CEO))
        self.assertEqual("CEO", token_type_str("TokenType.CEO"))

    def test_get_primary_character(self):
        primary = user_primary_character(self.user)
        self.assertIsNone(primary)

        char = self.make_character(self.user, 123456, "Test Char")

        epc = EvePrimaryCharacter.objects.create(
            character=char,
        )

        primary = user_primary_character(self.user)
        self.assertEqual("Test Char", primary.character_name)

        EvePrimaryCharacter.objects.create(
            character=char,
        )

        primary = user_primary_character(self.user)
        self.assertEqual("Test Char", primary.character_name)

        epc.user = self.user
        primary = user_primary_character(self.user)
        self.assertEqual("Test Char", primary.character_name)

    def test_get_user_characters(self):
        chars = user_characters(self.user)
        self.assertEqual(0, len(chars))

        self.make_character(self.user, 123456, "Test Char 1")

        chars = user_characters(self.user)
        self.assertEqual(1, len(chars))

        self.make_character(self.user, 234567, "Test Char 2")

        chars = user_characters(self.user)
        self.assertEqual(2, len(chars))

    def test_get_character(self):
        self.make_superuser()

        char = self.make_character(self.user, 123456, "Test Char")
        EvePrimaryCharacter.objects.create(
            character=char,
            user=self.user,
        )
        response = self.client.get(
            f"{BASE_URL}{char.character_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)

    def test_change_primary_character(self):
        self.make_superuser()

        char1 = self.make_character(self.user, 123456, "Test Char 1")

        response = self.client.put(
            f"{BASE_URL}primary?character_id={char1.character_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            "Test Char 1", user_primary_character(self.user).character_name
        )

        char2 = self.make_character(self.user, 123457, "Test Char 2")

        response = self.client.put(
            f"{BASE_URL}primary?character_id={char2.character_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            "Test Char 2", user_primary_character(self.user).character_name
        )
