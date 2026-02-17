import random
import factory
import logging

from typing import List
from unittest.mock import patch, MagicMock

from django.db.models import signals
from django.db.utils import IntegrityError
from django.contrib.auth.models import User
from esi.models import Token, Scope

from app.test import TestCase
from eveuniverse.models import EveType
from eveonline.client import EsiResponse
from eveonline.models import (
    EvePlayer,
    EveCharacter,
    EveCharacterSkill,
    EveSkillset,
    EveLocation,
)
from eveonline.signals import populate_eve_character_public_data
from eveonline.helpers.characters import upsert_character_skill

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


class SkillsUpdateTestCase(TestCase):
    """
    Tests methods of EveCharacterSkills update
    """

    def test_update_character_skills(self):
        char = EveCharacter.objects.create(
            character_id=123, character_name="Test Character 1"
        )
        EveType.objects.create(
            id=234,
            name="Skill 234",
            published=True,
            eve_group_id=1,
        )
        esi_skill = {
            "skill_id": 234,
            "skill_name": "Skill 234",
            "skillpoints_in_skill": 1000,
            "trained_skill_level": 2,
        }

        # First update will create the skill

        self.assertEqual(0, EveCharacterSkill.objects.count())

        upsert_character_skill(char, esi_skill)

        self.assertEqual(1, EveCharacterSkill.objects.count())

        # Second update will update the skill

        esi_skill["skillpoints_in_skill"] = 2000

        upsert_character_skill(char, esi_skill)

        self.assertEqual(1, EveCharacterSkill.objects.count())

        # Manually create a duplicate

        EveCharacterSkill.objects.create(
            character=char,
            skill_id=234,
            skill_name="Duplicate",
            skill_points=0,
            skill_level=0,
        )

        self.assertEqual(2, EveCharacterSkill.objects.count())

        esi_skill["skillpoints_in_skill"] = 3000

        # Update with duplicate will delete a copy

        upsert_character_skill(char, esi_skill)

        self.assertEqual(1, EveCharacterSkill.objects.count())


def characters(player: EvePlayer) -> List[EveCharacter]:
    return EveCharacter.objects.filter(user=player.user)


class EvePlayerTestCase(TestCase):
    """
    Tests the EvePlayer database model
    """

    def test_eveplayer(self):
        self.user.username = "somebody"
        self.user.save()

        character = EveCharacter.objects.create(
            character_id=123,
            character_name="Testpilot",
            user=self.user,
        )

        player = EvePlayer.objects.create(
            nickname="Nobody",
            primary_character=character,
            user=self.user,
        )

        self.assertEqual(1, EvePlayer.objects.count())

        self.assertEqual("somebody / Testpilot", str(player))
        self.assertEqual(123, player.primary_character.character_id)
        self.assertEqual(1, len(characters(player)))
        self.assertEqual("Testpilot", characters(player)[0].character_name)

    def test_duplicate_eveplayer_user_rejected(self):
        EvePlayer.objects.create(
            nickname="Player 1",
            user=self.user,
        )
        with self.assertRaises(IntegrityError):
            EvePlayer.objects.create(
                nickname="Player 2",
                user=self.user,
            )

    def test_duplicate_eveplayer_char_rejected(self):
        user2 = User.objects.create_user(username="User 2")

        character = EveCharacter.objects.create(
            character_id=123,
            character_name="Testpilot",
            user=self.user,
        )

        EvePlayer.objects.create(
            nickname="Player 1",
            user=self.user,
            primary_character=character,
        )
        with self.assertRaises(IntegrityError):
            EvePlayer.objects.create(
                nickname="Player 2",
                user=user2,
                primary_character=character,
            )


class EveLocationTestCase(TestCase):
    """
    Tests the EveLocation database model
    """

    def test_evelocation(self):
        EveLocation.objects.create(
            location_id=1234567890,
            location_name="Homebase",
            solar_system_id=1,
            solar_system_name="Home",
            short_name="Home",
            market_active=True,
            freight_active=False,
            staging_active=True,
        )

        self.assertEqual(1, EveLocation.objects.count())


class EveCharacterTestCase(TestCase):
    """
    Unit tests for the EveCharacter model
    """

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.signals.esi_public")
    def test_populate_eve_character_public_data(self, esi_public):
        esi_public.return_value.get_character_public_data.return_value = (
            EsiResponse(
                response_code=200,
                data={
                    "name": "Bob",
                    "corporation_id": 2001,
                },
            )
        )

        instance = EveCharacter.objects.create(
            character_id=1001,
        )
        populate_eve_character_public_data(MagicMock(), instance, True)

        saved_char = EveCharacter.objects.get(character_id=1001)
        self.assertEqual("Bob", saved_char.character_name)
        self.assertEqual(2001, saved_char.corporation_id)
