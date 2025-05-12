from django.db.models import signals
from app.test import TestCase
from eveonline.models import (
    EveCharacter,
    EveCharacterSkill,
    EveSkillset,
)
from eveonline.helpers.skills import compare_skills_to_skillset


class EveSkillsHelperTestCase(TestCase):
    """Tests for the EveSkills helpers"""

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

    def test_compare_skills_to_skillset(self):
        char = EveCharacter.objects.create(
            character_id=1234, character_name="Test Char"
        )
        EveCharacterSkill.objects.create(
            character=char,
            skill_id=1,
            skill_name="First",
            skill_level=3,
            skill_points=0,
        )
        skillset = EveSkillset.objects.create(
            name="Set 1",
            total_skill_points=1000000,
            skills="""
            First II
            """,
        )
        missing, progress = compare_skills_to_skillset(
            char.character_id, skillset
        )
        self.assertEqual(0, len(missing))
        self.assertEqual(100, progress)

        skillset2 = EveSkillset.objects.create(
            name="Set 2",
            total_skill_points=3000000,
            skills="""
            First II
            Second V
            """,
        )
        missing, progress = compare_skills_to_skillset(
            char.character_id,
            skillset2,
        )
        self.assertEqual(1, len(missing))
