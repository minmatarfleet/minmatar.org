"""Tests for character reprocessing skill / implant refine resolution."""

from django.test import TestCase

from eveonline.models import EveCharacter, EveCharacterClone, EveCharacterSkill
from industry.helpers.facility_profiles import get_facility_refine_rate
from industry.helpers.reprocessing_skills import (
    MAX_REPROCESSING_IMPLANT_BONUS,
    SKILL_COHERENT_ORE_PROCESSING,
    SKILL_REPROCESSING,
    SKILL_REPROCESSING_EFFICIENCY,
    SKILL_SIMPLE_ORE_PROCESSING,
    SKILL_UBIQUITOUS_MOON_ORE_PROCESSING,
    compression_ore_refine_yields,
    resolve_character_reprocessing_skills,
    resolve_refine_rate,
)


class ReprocessingSkillsTestCase(TestCase):
    def setUp(self):
        self.char = EveCharacter.objects.create(
            character_id=2122000001,
            character_name="Refine Pilot",
        )

    def _set_skills(self, *, rep=5, eff=5, simple=5, coherent=5, ubiquitous=5):
        for sid, level, name in (
            (SKILL_REPROCESSING, rep, "Reprocessing"),
            (SKILL_REPROCESSING_EFFICIENCY, eff, "Reprocessing Efficiency"),
            (SKILL_SIMPLE_ORE_PROCESSING, simple, "Simple Ore Processing"),
            (
                SKILL_COHERENT_ORE_PROCESSING,
                coherent,
                "Coherent Ore Processing",
            ),
            (
                SKILL_UBIQUITOUS_MOON_ORE_PROCESSING,
                ubiquitous,
                "Ubiquitous Moon Ore Processing",
            ),
        ):
            EveCharacterSkill.objects.update_or_create(
                character=self.char,
                skill_id=sid,
                defaults={
                    "skill_name": name,
                    "skill_points": level * 1000,
                    "skill_level": level,
                },
            )

    def test_defaults_assume_max_skills_no_implant(self):
        rate, source, skills = resolve_refine_rate("amamake")
        self.assertEqual(source, "facility_default")
        self.assertIsNone(skills)
        expected = get_facility_refine_rate("amamake", implant=0.0)
        self.assertAlmostEqual(rate, expected, places=10)
        self.assertAlmostEqual(rate, 0.8247406585, places=7)

    def test_max_skills_with_implant_uses_rx804(self):
        rate, source, skills = resolve_refine_rate(
            "amamake", use_reprocessing_implants=True
        )
        self.assertEqual(source, "facility_default")
        self.assertIsNone(skills)
        expected = get_facility_refine_rate(
            "amamake", implant=MAX_REPROCESSING_IMPLANT_BONUS
        )
        self.assertAlmostEqual(rate, expected, places=10)
        self.assertAlmostEqual(MAX_REPROCESSING_IMPLANT_BONUS, 0.04)
        self.assertAlmostEqual(rate, 0.8577302848, places=7)

    def test_character_skills_lower_than_default(self):
        self._set_skills(rep=4, eff=4, simple=3, coherent=5)
        skills = resolve_character_reprocessing_skills(self.char)
        # Blend is Veldspar/Plagioclase (Simple) + Zeolites (Ubiquitous) → min.
        self.assertEqual(skills.ore_processing_level, 3)
        self.assertEqual(skills.simple_ore_processing_level, 3)
        self.assertEqual(skills.coherent_ore_processing_level, 5)
        self.assertEqual(skills.ubiquitous_moon_ore_processing_level, 5)
        self.assertEqual(skills.reprocessing_level, 4)
        self.assertEqual(skills.reprocessing_efficiency_level, 4)
        self.assertFalse(skills.use_reprocessing_implants)
        self.assertAlmostEqual(skills.effective_implant, 0.0)

        rate, source, resolved = resolve_refine_rate(
            "amamake", character=self.char
        )
        self.assertEqual(source, "character")
        self.assertIsNotNone(resolved)
        expected = get_facility_refine_rate(
            "amamake",
            reprocessing_level=4,
            reprocessing_efficiency_level=4,
            ore_processing_level=3,
            implant=0.0,
        )
        self.assertAlmostEqual(rate, expected, places=10)

    def test_missing_skills_treated_as_zero(self):
        skills = resolve_character_reprocessing_skills(self.char)
        self.assertEqual(skills.reprocessing_level, 0)
        self.assertEqual(skills.ore_processing_level, 0)

    def test_implant_toggle_off_ignores_fitted_rx(self):
        self._set_skills()
        EveCharacterClone.objects.create(
            character=self.char,
            clone_id=1,
            is_active=True,
            implants=[
                {
                    "type_id": 27174,
                    "type_name": "Zainou 'Beancounter' Reprocessing RX-804",
                    "estimated_price_isk": 1,
                }
            ],
        )
        skills = resolve_character_reprocessing_skills(self.char)
        self.assertAlmostEqual(skills.implant_bonus, 0.04)
        self.assertAlmostEqual(skills.effective_implant, 0.0)

        rate, _, _ = resolve_refine_rate("amamake", character=self.char)
        expected = get_facility_refine_rate("amamake", implant=0.0)
        self.assertAlmostEqual(rate, expected, places=10)

    def test_implant_toggle_on_applies_fitted_rx(self):
        self._set_skills()
        EveCharacterClone.objects.create(
            character=self.char,
            clone_id=1,
            is_active=True,
            implants=[
                {
                    "type_id": 27174,
                    "type_name": "Zainou 'Beancounter' Reprocessing RX-804",
                    "estimated_price_isk": 1,
                }
            ],
        )
        skills = resolve_character_reprocessing_skills(
            self.char, use_reprocessing_implants=True
        )
        self.assertTrue(skills.use_reprocessing_implants)
        self.assertAlmostEqual(skills.effective_implant, 0.04)
        self.assertEqual(skills.implant_type_id, 27174)

        rate, _, _ = resolve_refine_rate(
            "amamake",
            character=self.char,
            use_reprocessing_implants=True,
        )
        expected = get_facility_refine_rate("amamake", implant=0.04)
        self.assertAlmostEqual(rate, expected, places=10)

    def test_implant_toggle_on_no_rx_assumes_rx804(self):
        """Character selected, toggle ON, no RX anywhere → RX-804 fallback."""
        self._set_skills()
        EveCharacterClone.objects.create(
            character=self.char,
            clone_id=1,
            is_active=True,
            implants=[
                {
                    "type_id": 19540,
                    "type_name": "Cybernetic",
                    "estimated_price_isk": 1,
                }
            ],
        )
        skills = resolve_character_reprocessing_skills(
            self.char, use_reprocessing_implants=True
        )
        self.assertAlmostEqual(skills.implant_bonus, 0.0)
        self.assertIsNone(skills.implant_type_id)
        self.assertAlmostEqual(skills.effective_implant, 0.04)

        rate, _, _ = resolve_refine_rate(
            "amamake",
            character=self.char,
            use_reprocessing_implants=True,
        )
        expected = get_facility_refine_rate("amamake", implant=0.04)
        self.assertAlmostEqual(rate, expected, places=10)
        self.assertAlmostEqual(rate, 0.8577302848, places=7)

    def test_manual_override_wins(self):
        self._set_skills(rep=1, eff=1, simple=1, coherent=1)
        rate, source, skills = resolve_refine_rate(
            "amamake",
            character=self.char,
            use_reprocessing_implants=True,
            refine_rate_override=0.75,
        )
        self.assertEqual(source, "override")
        self.assertIsNone(skills)
        self.assertAlmostEqual(rate, 0.75)

    def test_invalid_override_raises(self):
        with self.assertRaises(ValueError):
            resolve_refine_rate("amamake", refine_rate_override=0)

    def test_best_rx_across_clones_and_active_implants(self):
        """Best RX wins; is_active is ignored."""
        self._set_skills()
        EveCharacterClone.objects.create(
            character=self.char,
            clone_id=1,
            is_active=True,
            implants=[
                {
                    "type_id": 27175,
                    "type_name": "Zainou 'Beancounter' Reprocessing RX-801",
                    "estimated_price_isk": 1,
                }
            ],
        )
        EveCharacterClone.objects.create(
            character=self.char,
            clone_id=2,
            is_active=False,
            implants=[
                {
                    "type_id": 27169,
                    "type_name": "Zainou 'Beancounter' Reprocessing RX-802",
                    "estimated_price_isk": 1,
                }
            ],
        )
        self.char.active_implants = [27174, 19540]
        self.char.save(update_fields=["active_implants"])

        skills = resolve_character_reprocessing_skills(
            self.char, use_reprocessing_implants=True
        )
        self.assertAlmostEqual(skills.effective_implant, 0.04)
        self.assertEqual(skills.implant_type_id, 27174)

        rate, _, _ = resolve_refine_rate(
            "amamake",
            character=self.char,
            use_reprocessing_implants=True,
        )
        expected = get_facility_refine_rate("amamake", implant=0.04)
        self.assertAlmostEqual(rate, expected, places=10)

    def test_inactive_clone_rx_used_when_active_clone_has_none(self):
        """Active clone without RX must not block RX on another clone."""
        self._set_skills()
        EveCharacterClone.objects.create(
            character=self.char,
            clone_id=1,
            is_active=True,
            implants=[
                {
                    "type_id": 19540,
                    "type_name": "Cybernetic",
                    "estimated_price_isk": 1,
                }
            ],
        )
        EveCharacterClone.objects.create(
            character=self.char,
            clone_id=2,
            is_active=False,
            implants=[
                {
                    "type_id": 27174,
                    "type_name": "Zainou 'Beancounter' Reprocessing RX-804",
                    "estimated_price_isk": 1,
                }
            ],
        )
        skills = resolve_character_reprocessing_skills(
            self.char, use_reprocessing_implants=True
        )
        self.assertAlmostEqual(skills.effective_implant, 0.04)
        self.assertEqual(skills.implant_type_id, 27174)

    def test_esi_active_implants_contribute(self):
        """ESI active_implants counted even when jump clones have weaker RX."""
        self._set_skills()
        EveCharacterClone.objects.create(
            character=self.char,
            clone_id=1,
            is_active=False,
            implants=[
                {
                    "type_id": 27175,
                    "type_name": "Zainou 'Beancounter' Reprocessing RX-801",
                    "estimated_price_isk": 1,
                }
            ],
        )
        self.char.active_implants = [27174, 19540]
        self.char.save(update_fields=["active_implants"])

        skills = resolve_character_reprocessing_skills(
            self.char, use_reprocessing_implants=True
        )
        self.assertAlmostEqual(skills.effective_implant, 0.04)
        self.assertEqual(skills.implant_type_id, 27174)

        rate, _, _ = resolve_refine_rate(
            "amamake",
            character=self.char,
            use_reprocessing_implants=True,
        )
        expected = get_facility_refine_rate("amamake", implant=0.04)
        self.assertAlmostEqual(rate, expected, places=10)

    def test_best_rx_among_jump_clones(self):
        """Best RX among jump clones when active_implants empty."""
        self._set_skills()
        EveCharacterClone.objects.create(
            character=self.char,
            clone_id=1,
            is_active=False,
            implants=[
                {
                    "type_id": 27175,
                    "type_name": "Zainou 'Beancounter' Reprocessing RX-801",
                    "estimated_price_isk": 1,
                }
            ],
        )
        EveCharacterClone.objects.create(
            character=self.char,
            clone_id=2,
            is_active=False,
            implants=[
                {
                    "type_id": 27174,
                    "type_name": "Zainou 'Beancounter' Reprocessing RX-804",
                    "estimated_price_isk": 1,
                }
            ],
        )
        skills = resolve_character_reprocessing_skills(
            self.char, use_reprocessing_implants=True
        )
        self.assertAlmostEqual(skills.effective_implant, 0.04)
        self.assertEqual(skills.implant_type_id, 27174)

    def test_compression_ore_yields_split_simple_vs_ubiquitous(self):
        """Veldspar/Plagioclase use Simple; Zeolites use Ubiquitous."""
        self._set_skills(rep=5, eff=5, simple=3, coherent=5, ubiquitous=5)
        skills = resolve_character_reprocessing_skills(self.char)
        yields = compression_ore_refine_yields("amamake", skills=skills)
        by_ore = {row.ore_name: row for row in yields}
        self.assertEqual(set(by_ore), {"Veldspar", "Zeolites", "Plagioclase"})

        self.assertEqual(
            by_ore["Veldspar"].skill_name, "Simple Ore Processing"
        )
        self.assertEqual(by_ore["Veldspar"].skill_level, 3)
        self.assertEqual(
            by_ore["Plagioclase"].skill_name, "Simple Ore Processing"
        )
        self.assertEqual(by_ore["Plagioclase"].skill_level, 3)
        self.assertEqual(
            by_ore["Zeolites"].skill_name, "Ubiquitous Moon Ore Processing"
        )
        self.assertEqual(by_ore["Zeolites"].skill_level, 5)

        simple_rate = get_facility_refine_rate(
            "amamake",
            reprocessing_level=5,
            reprocessing_efficiency_level=5,
            ore_processing_level=3,
            implant=0.0,
        )
        ubi_rate = get_facility_refine_rate(
            "amamake",
            reprocessing_level=5,
            reprocessing_efficiency_level=5,
            ore_processing_level=5,
            implant=0.0,
        )
        self.assertAlmostEqual(
            by_ore["Veldspar"].refine_rate, simple_rate, places=10
        )
        self.assertAlmostEqual(
            by_ore["Plagioclase"].refine_rate, simple_rate, places=10
        )
        self.assertAlmostEqual(
            by_ore["Zeolites"].refine_rate, ubi_rate, places=10
        )
        self.assertGreater(ubi_rate, simple_rate)

        # Blend rate used for planning is the conservative min (Simple).
        blend, _, _ = resolve_refine_rate("amamake", character=self.char)
        self.assertAlmostEqual(blend, simple_rate, places=10)

    def test_compression_ore_yields_max_skills_default(self):
        yields = compression_ore_refine_yields("amamake")
        expected = get_facility_refine_rate("amamake", implant=0.0)
        self.assertEqual(len(yields), 3)
        for row in yields:
            self.assertEqual(row.skill_level, 5)
            self.assertAlmostEqual(row.refine_rate, expected, places=10)
