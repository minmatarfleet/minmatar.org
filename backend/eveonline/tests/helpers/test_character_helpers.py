import factory

from django.db.models import signals
from esi.models import Token

from app.test import TestCase

from eveonline.helpers.characters import (
    character_configured_scope_groups,
    character_desired_scopes,
    merge_scope_groups,
    related_characters,
    scope_groups_for_token_add,
)
from eveonline.models import EveCharacter
from eveonline.scopes import (
    TokenType,
    scope_names,
    scopes_for,
    scopes_for_groups,
    add_scopes,
    token_satisfies_type,
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

        self.assertEqual(28, len(scope_names(char.token)))

        self.assertEqual(37, len(scopes_for(TokenType.EXECUTOR)))

    def test_merge_scope_groups(self):
        self.assertEqual(
            ["Basic", "Industry"],
            merge_scope_groups(["Basic"], "Industry"),
        )
        self.assertEqual(
            ["Basic", "Director"],
            merge_scope_groups(["Basic"], "CEO"),
        )

    def test_character_configured_scope_groups(self):
        char = EveCharacter.objects.create(
            character_id=10002,
            character_name="Director Alt",
            esi_token_level="Director",
            esi_scope_groups=["Basic"],
        )
        self.assertEqual(
            ["Basic", "Director"],
            character_configured_scope_groups(char),
        )

    def test_token_satisfies_type(self):
        char = EveCharacter.objects.create(
            character_id=10003,
            character_name="Industry Alt",
        )
        token = Token.objects.create(
            user=self.user,
            character_id=char.character_id,
        )
        add_scopes(TokenType.INDUSTRY, token)
        self.assertTrue(token_satisfies_type(token, TokenType.INDUSTRY))
        self.assertFalse(token_satisfies_type(token, TokenType.DIRECTOR))

    def test_scope_groups_for_token_add(self):
        char = EveCharacter.objects.create(
            character_id=10004,
            character_name="Director Alt",
            esi_token_level="Director",
            esi_scope_groups=["Basic"],
        )
        self.assertEqual(
            ["Basic", "Director", "Industry"],
            scope_groups_for_token_add(char, TokenType.INDUSTRY),
        )
        self.assertEqual(
            len(scopes_for_groups(["Basic", "Director", "Industry"])),
            len(
                set(scopes_for(TokenType.DIRECTOR))
                | set(scopes_for(TokenType.INDUSTRY))
            ),
        )

    def test_related_characters_returns_same_user_characters(self):
        """related_characters returns all characters for the given character's user."""
        char_a = EveCharacter.objects.create(
            character_id=20001,
            character_name="Alpha",
            user=self.user,
        )
        EveCharacter.objects.create(
            character_id=20002,
            character_name="Beta",
            user=self.user,
        )
        related = related_characters(char_a)
        self.assertEqual(len(related), 2)
        self.assertCountEqual(
            [c.character_id for c in related], [20001, 20002]
        )
        self.assertEqual(
            [c.character_name for c in related], ["Alpha", "Beta"]
        )

    def test_related_characters_empty_when_no_user(self):
        """related_characters returns empty list when character has no user."""
        char = EveCharacter.objects.create(
            character_id=20003,
            character_name="Orphan",
            user=None,
        )
        self.assertEqual(related_characters(char), [])

    def test_related_characters_none_returns_empty(self):
        """related_characters returns empty list when passed None."""
        self.assertEqual(related_characters(None), [])
