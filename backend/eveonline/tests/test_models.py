import random
import factory
from django.db.models import signals
from app.test import TestCase
from eveonline.models import EveSkillset, EveCharacter, EveCharacterSkill


class EveSkillsetTestCase(TestCase):
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
            skill_level=2,
            skill_id=random.randint(1, 1000),
            skill_points=random.randint(1, 1000),
        )
        EveCharacterSkill.objects.create(
            character=EveCharacter.objects.get(character_id=125),
            skill_name="Electronic Warfare",
            skill_level=3,
            skill_id=random.randint(1, 1000),
            skill_points=random.randint(1, 1000),
        )
        EveCharacter.objects.create(
            character_id=126, character_name="Test Character 3"
        )

        result = skillset.get_number_of_characters_with_skillset()
        self.assertEqual(len(result), 2)
        self.assertTrue("Test Character 1" in result)
        self.assertTrue("Test Character 2" in result)
        self.assertFalse("Test Character 3" in result)
        self.assertFalse("Test Character 4" in result)
