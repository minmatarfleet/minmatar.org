from django.contrib.auth.models import Permission
from django.db.models import signals
from django.test import Client
from esi.models import Token

from app.test import TestCase
from eveonline.models import EveCharacter

BASE_URL = "/api/eveonline/characters/"


class CharacterRouterTestCase(TestCase):
    """Test cases for the character router."""

    def setUp(self):
        # disconnect signals
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )

        # create test client
        self.client = Client()

        super().setUp()

    def test_get_characters_success(self):
        response = self.client.get(
            BASE_URL, HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_get_characters_success_multiple_characters(self):
        token = Token.objects.create(
            character_id=123,
            user=self.user,
        )
        character = EveCharacter.objects.get(character_id=123)
        character.token = token
        character.save()

        # create another character not owned by user
        EveCharacter.objects.create(character_id=456)

        response = self.client.get(
            BASE_URL, HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "character_id": character.character_id,
                    "character_name": character.character_name,
                }
            ],
        )

    def test_get_characters_failure_unauthorized(self):
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, 401)

    def test_get_character_by_id_success(self):
        token = Token.objects.create(
            character_id=123,
            user=self.user,
        )
        character = EveCharacter.objects.get(character_id=123)
        character.token = token
        character.save()
        response = self.client.get(
            f"{BASE_URL}{character.character_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "character_id": character.character_id,
                "character_name": character.character_name,
                "skills": {},
            },
        )

    def test_get_character_by_id_success_override_permission(self):
        character = EveCharacter.objects.create(character_id=123)
        permission = Permission.objects.get(codename="view_evecharacter")
        self.user.user_permissions.add(permission)
        self.user.save()
        response = self.client.get(
            f"{BASE_URL}{character.character_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "character_id": character.character_id,
                "character_name": character.character_name,
                "skills": {},
            },
        )

    def test_get_character_by_id_failure_not_found(self):
        response = self.client.get(
            f"{BASE_URL}123", HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 404)

    def test_get_character_by_id_failure_unauthorized(self):
        character = EveCharacter.objects.create(character_id=123)
        response = self.client.get(f"{BASE_URL}{character.character_id}")
        self.assertEqual(response.status_code, 401)
