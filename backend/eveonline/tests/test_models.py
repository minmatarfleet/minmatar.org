import random
import factory
import logging
from django.db.models import signals
from django.contrib.auth.models import User

from app.test import TestCase
from eveonline.models import (
    EveCharacter,
    EveCharacterSkill,
    EveSkillset,
    Token,
    Scope,
)


logger = logging.getLogger("test.models")


class EveSkillsetTestCase(TestCase):
    """
    Tests methods of the EveSkillset model.
    """

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_get_missing_skills_for_character_id(self):
        skill_list = """
        Drones II
        Drones III
        Drones IV
        Electronic Warfare II
        Electronic Warfare III
        Electronic Warfare IV
        Advanced Drone Avionics I
        Advanced Drone Avionics II
        Advanced Drone Avionics III
        Advanced Drone Avionics IV
        """
        character = EveCharacter.objects.create(
            character_id=123, character_name="Test Character"
        )
        skillset = EveSkillset.objects.create(
            name="Test Skillset", skills=skill_list, total_skill_points=1
        )

        EveCharacterSkill.objects.create(
            character=character,
            skill_name="Drones",
            skill_level=5,
            skill_id=random.randint(1, 1000),
            skill_points=random.randint(1, 1000),
        )

        EveCharacterSkill.objects.create(
            character=character,
            skill_name="Electronic Warfare",
            skill_level=3,
            skill_id=random.randint(1, 1000),
            skill_points=random.randint(1, 1000),
        )

        result = skillset.get_missing_skills_for_character_id(
            character.character_id
        )
        expected_missing_skills = [
            "Electronic Warfare 4",
            "Advanced Drone Avionics 1",
            "Advanced Drone Avionics 2",
            "Advanced Drone Avionics 3",
            "Advanced Drone Avionics 4",
        ]
        self.assertEqual(result, expected_missing_skills)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_get_number_of_characters_with_skillset(self):
        skill_list = """
        Drones II
        Electronic Warfare II
        Electronic Warfare III
        Electronic Warfare IV
        """

        skillset = EveSkillset.objects.create(
            name="Test Skillset", skills=skill_list, total_skill_points=1
        )

        # create 2 characters with skillset and 1 without
        EveCharacter.objects.create(
            character_id=123, character_name="Test Character 1"
        )
        EveCharacterSkill.objects.create(
            character=EveCharacter.objects.get(character_id=123),
            skill_name="Drones",
            skill_level=2,
            skill_id=random.randint(1, 1000),
            skill_points=random.randint(1, 1000),
        )
        EveCharacterSkill.objects.create(
            character=EveCharacter.objects.get(character_id=123),
            skill_name="Electronic Warfare",
            skill_level=4,
            skill_id=random.randint(1, 1000),
            skill_points=random.randint(1, 1000),
        )

        EveCharacter.objects.create(
            character_id=124, character_name="Test Character 2"
        )
        EveCharacterSkill.objects.create(
            character=EveCharacter.objects.get(character_id=124),
            skill_name="Drones",
            skill_level=2,
            skill_id=random.randint(1, 1000),
            skill_points=random.randint(1, 1000),
        )
        EveCharacterSkill.objects.create(
            character=EveCharacter.objects.get(character_id=124),
            skill_name="Electronic Warfare",
            skill_level=4,
            skill_id=random.randint(1, 1000),
            skill_points=random.randint(1, 1000),
        )

        EveCharacter.objects.create(
            character_id=125, character_name="Test Character 3"
        )
        EveCharacterSkill.objects.create(
            character=EveCharacter.objects.get(character_id=125),
            skill_name="Drones",
            skill_level=1,
            skill_id=random.randint(1, 1000),
            skill_points=random.randint(1, 1000),
        )
        EveCharacterSkill.objects.create(
            character=EveCharacter.objects.get(character_id=125),
            skill_name="Electronic Warfare",
            skill_level=1,
            skill_id=random.randint(1, 1000),
            skill_points=random.randint(1, 1000),
        )
        EveCharacter.objects.create(
            character_id=126, character_name="Test Character 4"
        )

        result = skillset.get_number_of_characters_with_skillset()
        self.assertTrue("Test Character 1" in result)
        self.assertTrue("Test Character 2" in result)
        self.assertFalse("Test Character 3" in result)
        self.assertFalse("Test Character 4" in result)
        self.assertEqual(len(result), 2)


class TokenScopeTestCase(TestCase):
    """
    Tests methods for ESI token scopes.
    """

    def test_find_token_with_one_scope(self):
        EveCharacter.objects.create(
            character_id=123, character_name="Test Character 1"
        )
        user = User.objects.first()

        scope1 = Scope.objects.create(name="scope1", help_text="")
        scope2 = Scope.objects.create(name="scope2", help_text="")
        scope3 = Scope.objects.create(name="scope3", help_text="")
        Scope.objects.create(name="scope_unused", help_text="")

        token1 = Token(user=user, character_id=123, character_name="Token1")
        token1.save()
        token1.scopes.add(scope1, scope2)

        token2 = Token(user=user, character_id=123, character_name="Token2")
        token2.save()
        token2.scopes.add(scope2, scope3)

        self.assertEqual(2, Token.objects.count())

        token = Token.objects.filter(character_name="Token1").get()
        self.assertEqual(2, token.scopes.count())

        tokens = Token.objects.filter(
            character_id=123, scopes__name__in=["scope1"]
        )
        self.assertEqual(1, tokens.count())

        tokens = Token.objects.filter(
            character_id=123, scopes__name__in=["scope1", "scope2"]
        )
        # Note that this returns 3 tokens, even though there are only 2 in the database
        self.assertEqual(3, tokens.count())

        tokens = Token.objects.filter(
            character_id=123, scopes__name__in=["scope1", "scope2"]
        ).distinct()
        # Note that this returns 2 tokens, even though there are only 1 has those 2 scopes
        self.assertEqual(2, tokens.count())

        token = Token.get_token(123, ["scope1", "scope2"])
        self.assertEqual("Token1", token.character_name)

        token = Token.get_token(123, ["scope2", "scope3"])
        self.assertEqual("Token2", token.character_name)

        token = Token.get_token(123, ["scope1", "scope3"])
        self.assertFalse(token)

        token = Token.get_token(123, ["scope1", "scope_unused"])
        self.assertFalse(token)
