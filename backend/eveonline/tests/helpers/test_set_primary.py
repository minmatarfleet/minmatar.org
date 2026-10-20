"""Setting a main must not take it off another account."""

from django.contrib.auth.models import User
from django.http import HttpRequest
from django.test import TestCase

from discord.models import DiscordUser
from eveonline.endpoints.characters._helpers import (
    handle_add_character_esi_callback,
)
from eveonline.helpers.characters import (
    PrimaryCharacterHeld,
    set_primary_character,
)
from eveonline.models import EveCharacter, EvePlayer
from eveonline.scopes import TokenType
from esi.models import Token


class SetPrimaryHeldTestCase(TestCase):
    def test_refuses_to_take_another_accounts_main(self):
        previous = User.objects.create(username="previous-account")
        claimer = User.objects.create(username="claimer-account")
        DiscordUser.objects.create(
            id=101, discord_tag="held-pilot#0", user=previous
        )
        DiscordUser.objects.create(
            id=202, discord_tag="current-pilot#1234", user=claimer
        )
        character = EveCharacter.objects.create(
            character_id=9001,
            character_name="Moved Pilot",
            user=claimer,
        )
        stale = EvePlayer.objects.create(
            user=previous,
            nickname="Moved Pilot",
            primary_character=character,
        )
        EvePlayer.objects.create(user=claimer, nickname="claimer-account")

        with self.assertRaises(PrimaryCharacterHeld) as raised:
            set_primary_character(claimer, character)

        message = str(raised.exception)
        self.assertIn("held-pilot", message)
        self.assertIn("current-pilot#1234", message)
        self.assertIn("delete that account", message)
        stale.refresh_from_db()
        claimer_player = EvePlayer.objects.get(user=claimer)
        self.assertEqual(stale.primary_character_id, character.pk)
        self.assertEqual(stale.nickname, "Moved Pilot")
        self.assertIsNone(claimer_player.primary_character_id)

    def test_keeps_another_accounts_nickname(self):
        previous = User.objects.create(username="old-nick")
        claimer = User.objects.create(username="new-main")
        character = EveCharacter.objects.create(
            character_id=42,
            character_name="Moved Pilot",
            user=claimer,
        )
        stale = EvePlayer.objects.create(
            user=previous,
            nickname="moved pilot",
        )

        set_primary_character(claimer, character)

        stale.refresh_from_db()
        claimer_player = EvePlayer.objects.get(user=claimer)
        self.assertEqual(stale.nickname, "moved pilot")
        self.assertEqual(claimer_player.primary_character_id, character.pk)
        self.assertNotEqual(claimer_player.nickname.casefold(), "moved pilot")

    def test_add_character_does_not_move_a_main(self):
        previous = User.objects.create(username="previous-account")
        claimer = User.objects.create(username="claimer-account")
        DiscordUser.objects.create(
            id=303, discord_tag="held-pilot#0", user=previous
        )
        DiscordUser.objects.create(
            id=404, discord_tag="current-pilot#0", user=claimer
        )
        character = EveCharacter.objects.create(
            character_id=77,
            character_name="Moved Pilot",
            user=previous,
        )
        EvePlayer.objects.create(
            user=previous,
            nickname="Moved Pilot",
            primary_character=character,
        )
        token = Token.objects.create(
            user=claimer,
            character_id=77,
            character_name="Moved Pilot",
        )
        request = HttpRequest()
        request.user = claimer
        request.session = self.client.session
        request.session["redirect_url"] = "https://my.minmatar.org/account/"

        response = handle_add_character_esi_callback(
            request, token, TokenType.BASIC
        )

        character.refresh_from_db()
        self.assertEqual(character.user_id, previous.id)
        self.assertIn("error=main_held", response.url)
        self.assertIn("held=held-pilot", response.url)
        self.assertIn("current=current-pilot", response.url)
        self.assertFalse(Token.objects.filter(pk=token.pk).exists())
