import factory

from django.db.models import signals
from esi.models import Token

from app.test import TestCase

from eveonline.helpers.characters import character_desired_scopes
from eveonline.models import EveCharacter
from eveonline.scopes import (
    TokenType,
    scope_names,
    add_scopes,
    EXECUTOR_CHARACTER_SCOPES,
)


class CharacterHelperTests(TestCase):
    """Unit tests for character helpers"""

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_character_desired_scopes(self):
        char = EveCharacter.objects.create(
            character_id=10001,
            character_name="Test Pilot",
            esi_token_level="Basic",
        )
        char.token = Token.objects.create(
            user=self.user,
            character_id=char.character_id,
        )
        char.save()

        self.assertEqual(11, len(character_desired_scopes(char)))

        self.assertEqual(0, len(scope_names(char.token)))

        add_scopes(TokenType.DIRECTOR, char.token)

        self.assertEqual(16, len(scope_names(char.token)))

        self.assertEqual(33, len(EXECUTOR_CHARACTER_SCOPES))
