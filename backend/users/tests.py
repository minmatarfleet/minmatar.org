from app.test import TestCase
from django.db.models import signals
from django.test import Client
from eveonline.models import (
    EveCharacter,
    EvePrimaryCharacter,
    EveCorporation,
    EveAlliance,
)
from esi.models import Token
from discord.models import DiscordUser

# Create your tests here.
BASE_URL = "/api/users/"


class UserRouterTestCase(TestCase):
    def setUp(self):
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_private_data",
        )

        self.client = Client()

        super().setUp()

    def test_get_user_profile_success(self):
        self.maxDiff = None
        user = self.user
        Token.objects.create(
            character_id=634915984,
            user=user,
        )
        alliance = EveAlliance.objects.create(
            alliance_id=99011978,
            name="Test Alliance",
        )
        corporation = EveCorporation.objects.create(
            corporation_id=98726134,
            name="Test Corporation",
            alliance=alliance,
        )

        character = EveCharacter.objects.get(
            character_id=634915984
        )
        character.corporation = corporation
        character.save()
        discord_user = DiscordUser.objects.create(
            user=user,
            id=123,
            discord_tag="test#1234",
        )
        primary_character = EvePrimaryCharacter.objects.create(
            character=character
        )

        response = self.client.get(
            f"{BASE_URL}{self.user.id}/profile",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "user_id": user.id,
                "username": user.username,
                "permissions": [],
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
                "eve_character_profile": {
                    "character_id": primary_character.character.character_id,
                    "character_name": primary_character.character.character_name,
                    "corporation_id": primary_character.character.corporation.corporation_id,
                    "corporation_name": primary_character.character.corporation.name,
                    "alliance_id": primary_character.character.corporation.alliance.alliance_id,
                    "alliance_name": primary_character.character.corporation.alliance.name,
                    "scopes": [],
                },
                "discord_user_profile": {
                    "id": discord_user.id,
                    "discord_tag": discord_user.discord_tag,
                    "avatar": f"https://cdn.discordapp.com/avatars/{discord_user.id}/{discord_user.avatar}.png",
                },
            },
        )
