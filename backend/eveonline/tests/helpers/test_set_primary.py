"""Setting a main must not 500 when another account still holds the name."""

from django.contrib.auth.models import User
from django.test import TestCase

from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter, EvePlayer


class SetPrimaryNicknameTestCase(TestCase):
    def test_releases_stale_primary_and_nickname(self):
        previous = User.objects.create(username="previous-account")
        claimer = User.objects.create(username="claimer-account")
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

        set_primary_character(claimer, character)

        stale.refresh_from_db()
        claimer_player = EvePlayer.objects.get(user=claimer)
        self.assertIsNone(stale.primary_character_id)
        self.assertNotEqual(stale.nickname.casefold(), "moved pilot")
        self.assertEqual(claimer_player.primary_character_id, character.pk)
        self.assertEqual(claimer_player.nickname, "Moved Pilot")

    def test_frees_nickname_when_primary_pointer_is_already_clear(self):
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
        self.assertNotEqual(stale.nickname.casefold(), "moved pilot")
        self.assertEqual(claimer_player.nickname, "Moved Pilot")
        self.assertEqual(claimer_player.primary_character_id, character.pk)
