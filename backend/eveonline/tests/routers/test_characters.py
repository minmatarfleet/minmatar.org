from django.db.models import signals
from django.http import HttpRequest
from django.test import Client
from django.contrib.auth.models import User

from esi.models import Token, Scope
from app.test import TestCase
from discord.models import DiscordUser
from eveonline.models import (
    EveCharacter,
    EvePrimaryCharacter,
    EvePrimaryCharacterChangeLog,
    EveCharacterLog,
    EveCharacterSkillset,
    EveSkillset,
    EveTag,
    EveCharacterTag,
)
from eveonline.scopes import TokenType, token_type_str
from eveonline.helpers.characters import (
    user_primary_character,
    user_characters,
)
from eveonline.routers.characters import (
    handle_add_character_esi_callback,
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
            user=user,
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

    def make_token(self, char_id: int) -> Token:
        return Token.objects.create(
            character_id=char_id,
            character_name=f"TestChar {char_id}",
            character_owner_hash=f"new hash {char_id}",
        )

    def make_request(
        self, redirect_url: str = "/", add_char_id=None
    ) -> HttpRequest:
        req = HttpRequest()
        req.user = self.user
        req.session = self.client.session
        req.session["redirect_url"] = redirect_url
        if add_char_id:
            req.session["add_character_id"] = str(add_char_id)
        else:
            req.session.pop("add_character_id", None)
        return req

    def test_add_esi_character_new(self):
        char_id = 1234
        req = self.make_request()
        token = self.make_token(char_id)

        handle_add_character_esi_callback(req, token, TokenType.BASIC)

        new_char = EveCharacter.objects.filter(character_id=char_id).first()
        self.assertEqual(f"TestChar {char_id}", new_char.character_name)
        self.assertEqual("Basic", new_char.esi_token_level)
        self.assertFalse(new_char.esi_suspended)
        self.assertEqual(char_id, new_char.token.character_id)
        self.assertEqual(
            f"new hash {char_id}", new_char.token.character_owner_hash
        )

    def test_add_esi_character_update(self):
        char_id = 2345
        self.make_character(self.user, char_id, "TestChar 2345")

        req = self.make_request("/", char_id)
        token = self.make_token(char_id)

        handle_add_character_esi_callback(req, token, TokenType.BASIC)

        new_char = EveCharacter.objects.filter(character_id=char_id).first()
        self.assertEqual(f"TestChar {char_id}", new_char.character_name)
        self.assertEqual("Basic", new_char.esi_token_level)
        self.assertFalse(new_char.esi_suspended)
        self.assertEqual(char_id, new_char.token.character_id)
        self.assertEqual(
            f"new hash {char_id}", new_char.token.character_owner_hash
        )

        log = EveCharacterLog.objects.filter(
            username=self.user.username
        ).first()
        self.assertEqual(f"TestChar {char_id}", log.character_name)

    def test_add_esi_character_update_incorrect(self):
        char_id = 7890
        req = self.make_request("/testing", 1000)
        token = self.make_token(char_id)

        response = handle_add_character_esi_callback(
            req, token, TokenType.BASIC
        )

        self.assertEqual("/testing?error=wrong_character", response.url)

    def test_add_esi_character_update_no_token(self):
        char_id = 3456
        char = self.make_character(self.user, char_id, f"TestChar {char_id}")
        char.token.delete()
        char.token = None
        char.save()

        req = self.make_request()
        token = self.make_token(char_id)

        handle_add_character_esi_callback(req, token, TokenType.BASIC)

        new_char = EveCharacter.objects.filter(character_id=char_id).first()
        self.assertEqual(f"TestChar {char_id}", new_char.character_name)
        self.assertEqual("Basic", new_char.esi_token_level)
        self.assertFalse(new_char.esi_suspended)
        self.assertEqual(char_id, new_char.token.character_id)
        self.assertEqual(
            f"new hash {char_id}", new_char.token.character_owner_hash
        )

    def test_add_esi_character_update_less_scopes(self):
        char_id = 4567
        char = self.make_character(self.user, char_id, f"TestChar {char_id}")

        scope = Scope.objects.create(name="TestScope.1")

        self.assertEqual(0, len(char.token.scopes.all()))
        char.token.scopes.add(scope)
        char.token.character_owner_hash = "Old hash"
        char.token.save()
        self.assertEqual(1, len(char.token.scopes.all()))

        req = self.make_request()
        token = self.make_token(char_id)

        handle_add_character_esi_callback(req, token, TokenType.BASIC)

        new_char = EveCharacter.objects.filter(character_id=char_id).first()
        self.assertEqual(f"TestChar {char_id}", new_char.character_name)
        self.assertFalse(new_char.esi_suspended)
        self.assertEqual(char_id, new_char.token.character_id)
        self.assertEqual("Old hash", new_char.token.character_owner_hash)

    def test_get_skillsets(self):
        char_id = 5678
        char = self.make_character(self.user, char_id, f"TestChar {char_id}")

        skillset = EveSkillset.objects.create(
            name="Test skillset",
            skills="",
            total_skill_points=1234567,
        )
        EveCharacterSkillset.objects.create(
            eve_skillset=skillset,
            character=char,
            progress=0.6,
            missing_skills="[]",
        )

        response = self.client.get(
            f"{BASE_URL}{char_id}/skillsets",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        skillsets = response.json()
        self.assertEqual(1, len(skillsets))
        self.assertEqual("Test skillset", skillsets[0]["name"])
        self.assertAlmostEqual(0.6, skillsets[0]["progress"])

    def test_get_character_with_token_issue(self):
        char = self.make_character(self.user, 123456, "Test Char suspended")
        char.esi_suspended = True
        char.esi_token_level = "Super"
        char.save()

        DiscordUser.objects.create(
            user=self.user,
            id=1234,
            discord_tag="tag",
        )
        EvePrimaryCharacter.objects.create(
            character=char,
            user=self.user,
        )

        response = self.client.get(
            f"{BASE_URL}summary",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)

        data = response.json()

        chars = data["characters"]

        self.assertEqual(1, len(chars))
        self.assertEqual("SUSPENDED", chars[0]["token_status"])

    def test_character_summary_without_primary(self):
        char = self.make_character(self.user, 123456, "Test Char suspended")
        char.esi_token_level = "Super"
        char.save()

        DiscordUser.objects.create(
            user=self.user,
            id=1234,
            discord_tag="tag",
        )
        response = self.client.get(
            f"{BASE_URL}summary",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(1, len(data["characters"]))
        for char in data["characters"]:
            self.assertFalse(char["is_primary"])

    def test_get_character_tags(self):
        char = self.make_character(self.user, 123456, "Test Char")
        tag1 = EveTag.objects.create(title="Test 1", description="Desc 1")
        tag2 = EveTag.objects.create(title="Test 2", description="Desc 2")
        EveTag.objects.create(title="Test 3", description="Desc 3")

        response = self.client.get(
            f"{BASE_URL}tags",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": 1,
                    "title": "Test 1",
                    "description": "Desc 1",
                    "image_name": None,
                },
                {
                    "id": 2,
                    "title": "Test 2",
                    "description": "Desc 2",
                    "image_name": None,
                },
                {
                    "id": 3,
                    "title": "Test 3",
                    "description": "Desc 3",
                    "image_name": None,
                },
            ],
        )

        EveCharacterTag.objects.create(character=char, tag=tag1)
        EveCharacterTag.objects.create(character=char, tag=tag2)

        response = self.client.get(
            f"{BASE_URL}{char.character_id}/tags",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [
                {
                    "id": 1,
                    "title": "Test 1",
                    "description": "Desc 1",
                    "image_name": None,
                },
                {
                    "id": 2,
                    "title": "Test 2",
                    "description": "Desc 2",
                    "image_name": None,
                },
            ],
            response.json(),
        )

        response = self.client.post(
            f"{BASE_URL}{char.character_id}/tags",
            data=[3],
            content_type="text/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            f"{BASE_URL}{char.character_id}/tags",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [
                {
                    "id": 1,
                    "title": "Test 1",
                    "description": "Desc 1",
                    "image_name": None,
                },
                {
                    "id": 2,
                    "title": "Test 2",
                    "description": "Desc 2",
                    "image_name": None,
                },
                {
                    "id": 3,
                    "title": "Test 3",
                    "description": "Desc 3",
                    "image_name": None,
                },
            ],
            response.json(),
        )

        response = self.client.delete(
            f"{BASE_URL}{char.character_id}/tags/2",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            f"{BASE_URL}{char.character_id}/tags",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [
                {
                    "id": 1,
                    "title": "Test 1",
                    "description": "Desc 1",
                    "image_name": None,
                },
                {
                    "id": 3,
                    "title": "Test 3",
                    "description": "Desc 3",
                    "image_name": None,
                },
            ],
            response.json(),
        )
