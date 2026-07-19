"""Tests for industry.helpers.compressed_ore."""

from unittest.mock import patch

from django.test import TestCase

from eveonline.models import EveCharacter, EveCharacterSkill
from industry.helpers.compressed_ore import (
    COMPRESSION_COVERED_MINERALS,
    PRIMARY_BELT_ORE_FOR_MINERAL,
    MaterialBuckets,
    base_ore_name,
    belt_ore_compressed_volume_m3,
    best_belt_ore_for_mineral,
    build_compressed_ore_plan,
    compression_covered_materials,
    compute_practical_belt_blend,
    conservative_refine_rate,
    mineral_density,
    moon_ore_for_pi_p0,
    reprocess_output,
    to_compressed_units,
)
from industry.helpers.facility_profiles import get_facility_refine_rate
from industry.helpers.reprocessing_skills import resolve_refine_rate


def _standard_yields(refine: float = 0.84) -> dict:
    """Isolation-optimal set + fallbacks: Veld/Zeolites/Plagioclase + runners-up."""
    return {
        "Veldspar": {"Tritanium": 4.0 * refine},
        "Zeolites": {"Pyerite": 80.0 * refine, "Mexallon": 4.0 * refine},
        "Plagioclase": {"Tritanium": 1.75 * refine, "Mexallon": 0.7 * refine},
        "Scordite": {"Tritanium": 1.5 * refine, "Pyerite": 0.99 * refine},
        "Pyroxeres": {"Pyerite": 0.9 * refine, "Mexallon": 0.3 * refine},
        "Kernite": {"Mexallon": 0.6 * refine, "Isogen": 1.2 * refine},
    }


class MoonOreMathTestCase(TestCase):
    def test_moon_ore_scales_with_refine_rate(self):
        pi_p0 = {"Hydrocarbons": 6500}
        units_100, _ = moon_ore_for_pi_p0(
            pi_p0, refine_rate=1.0, require_market=False
        )
        units_84, _ = moon_ore_for_pi_p0(
            pi_p0, refine_rate=0.84, require_market=False
        )
        # 6500 / 0.65 = 10_000 units (1:1 with Compressed Bitumens)
        self.assertEqual(units_100["Bitumens"], 10_000)
        self.assertGreater(units_84["Bitumens"], units_100["Bitumens"])

    def test_moon_ore_for_pi_p0_byproducts(self):
        pi_p0 = {
            "Hydrocarbons": 9200,
            "Atmospheric Gases": 9200,
            "Evaporite Deposits": 1200,
            "Silicates": 1200,
        }
        moon_units, byproducts = moon_ore_for_pi_p0(
            pi_p0, refine_rate=1.0, require_market=False
        )
        self.assertEqual(moon_units["Bitumens"], 14_154)
        self.assertEqual(moon_units["Zeolites"], 14_154)
        self.assertAlmostEqual(byproducts["Pyerite"], 2_092_380, delta=50)
        self.assertAlmostEqual(byproducts["Mexallon"], 128_008, delta=20)


class OptimalOreSelectionTestCase(TestCase):
    def test_primary_ores_match_isolation_ranking(self):
        self.assertEqual(PRIMARY_BELT_ORE_FOR_MINERAL["Tritanium"], "Veldspar")
        self.assertEqual(PRIMARY_BELT_ORE_FOR_MINERAL["Pyerite"], "Zeolites")
        self.assertEqual(
            PRIMARY_BELT_ORE_FOR_MINERAL["Mexallon"], "Plagioclase"
        )

    def test_isolation_density_zeolites_beats_scordite_for_pye(self):
        yields = _standard_yields(1.0)
        self.assertGreater(
            mineral_density("Zeolites", "Pyerite", yields),
            mineral_density("Scordite", "Pyerite", yields),
        )
        self.assertGreater(
            mineral_density("Veldspar", "Tritanium", yields),
            mineral_density("Scordite", "Tritanium", yields),
        )
        self.assertEqual(
            best_belt_ore_for_mineral("Tritanium", yields), "Veldspar"
        )
        self.assertEqual(
            best_belt_ore_for_mineral("Pyerite", yields), "Zeolites"
        )

    def test_isolation_density_plagioclase_beats_kernite_for_mex(self):
        yields = _standard_yields(1.0)
        self.assertGreater(
            mineral_density("Plagioclase", "Mexallon", yields),
            mineral_density("Kernite", "Mexallon", yields),
        )
        self.assertGreater(
            mineral_density("Plagioclase", "Mexallon", yields),
            mineral_density("Pyroxeres", "Mexallon", yields),
        )
        self.assertGreater(
            mineral_density("Plagioclase", "Mexallon", yields),
            mineral_density("Zeolites", "Mexallon", yields),
        )
        self.assertEqual(
            best_belt_ore_for_mineral("Mexallon", yields), "Plagioclase"
        )

    def test_trit_only_uses_veldspar_not_scordite_or_zeolites(self):
        refine = 0.84
        belt, imports = compute_practical_belt_blend(
            {"Tritanium": 8_000_000}, {}, _standard_yields(refine)
        )
        self.assertIn("Veldspar", belt)
        self.assertNotIn("Scordite", belt)
        self.assertNotIn("Zeolites", belt)
        self.assertNotIn("Plagioclase", belt)
        self.assertEqual(imports.get("Tritanium", 0), 0)
        expected = 8_000_000 / (4.0 * refine)
        self.assertAlmostEqual(belt["Veldspar"], expected, delta=1)

    def test_pye_only_uses_zeolites_sized_for_pye(self):
        refine = 0.84
        pye_need = 4_000_000
        belt, imports = compute_practical_belt_blend(
            {"Pyerite": pye_need}, {}, _standard_yields(refine)
        )
        self.assertIn("Zeolites", belt)
        self.assertNotIn("Veldspar", belt)
        self.assertNotIn("Scordite", belt)
        self.assertNotIn("Plagioclase", belt)
        self.assertEqual(imports.get("Pyerite", 0), 0)
        expected = pye_need / (80.0 * refine)
        self.assertAlmostEqual(belt["Zeolites"], expected, delta=1)

    def test_mex_only_uses_plagioclase_not_kernite_or_zeolites(self):
        refine = 0.84
        mex_need = 1_000_000
        belt, imports = compute_practical_belt_blend(
            {"Mexallon": mex_need}, {}, _standard_yields(refine)
        )
        self.assertIn("Plagioclase", belt)
        self.assertNotIn("Kernite", belt)
        self.assertNotIn("Zeolites", belt)
        self.assertNotIn("Pyroxeres", belt)
        self.assertNotIn("Veldspar", belt)
        self.assertEqual(imports.get("Mexallon", 0), 0)
        expected = mex_need / (0.7 * refine)
        self.assertAlmostEqual(belt["Plagioclase"], expected, delta=1)

    def test_blend_zeolites_for_pye_veldspar_for_trit(self):
        refine = 0.84
        trit, pye = 8_000_000, 4_000_000
        yields = _standard_yields(refine)
        belt, imports = compute_practical_belt_blend(
            {"Tritanium": trit, "Pyerite": pye}, {}, yields
        )
        self.assertEqual(imports.get("Tritanium", 0), 0)
        self.assertEqual(imports.get("Pyerite", 0), 0)
        self.assertIn("Zeolites", belt)
        self.assertIn("Veldspar", belt)
        self.assertNotIn("Scordite", belt)
        self.assertNotIn("Plagioclase", belt)

        z_expected = pye / yields["Zeolites"]["Pyerite"]
        self.assertAlmostEqual(belt["Zeolites"], z_expected, delta=1)
        # Zeolites yield no Trit → full Trit from Veldspar.
        v_expected = trit / yields["Veldspar"]["Tritanium"]
        self.assertAlmostEqual(belt["Veldspar"], v_expected, delta=1)

    def test_blend_pye_mex_trit_credits_byproducts_in_order(self):
        """Pye→Zeolites, remaining Mex→Plagioclase, remaining Trit→Veldspar."""
        refine = 0.84
        trit, pye, mex = 8_000_000, 4_000_000, 600_000
        yields = _standard_yields(refine)
        belt, imports = compute_practical_belt_blend(
            {"Tritanium": trit, "Pyerite": pye, "Mexallon": mex}, {}, yields
        )
        self.assertEqual(imports.get("Tritanium", 0), 0)
        self.assertEqual(imports.get("Pyerite", 0), 0)
        self.assertEqual(imports.get("Mexallon", 0), 0)
        self.assertIn("Zeolites", belt)
        self.assertIn("Plagioclase", belt)
        self.assertIn("Veldspar", belt)
        self.assertNotIn("Kernite", belt)
        self.assertNotIn("Scordite", belt)

        z_units = pye / yields["Zeolites"]["Pyerite"]
        self.assertAlmostEqual(belt["Zeolites"], z_units, delta=1)
        mex_from_z = z_units * yields["Zeolites"]["Mexallon"]
        mex_remaining = mex - mex_from_z
        p_units = mex_remaining / yields["Plagioclase"]["Mexallon"]
        self.assertAlmostEqual(belt["Plagioclase"], p_units, delta=1)
        trit_from_p = p_units * yields["Plagioclase"]["Tritanium"]
        v_units = (trit - trit_from_p) / yields["Veldspar"]["Tritanium"]
        self.assertAlmostEqual(belt["Veldspar"], v_units, delta=1)

    def test_zeolites_beat_scordite_volume_and_trit_overage_for_pye_only(self):
        refine = 0.84
        yields = _standard_yields(refine)
        needs = {"Pyerite": 100_000_000}
        belt, _ = compute_practical_belt_blend(needs, {}, yields)
        zeolite_m3 = belt_ore_compressed_volume_m3(belt)

        scord_units = needs["Pyerite"] / yields["Scordite"]["Pyerite"]
        scord_m3 = belt_ore_compressed_volume_m3({"Scordite": scord_units})
        trit_overage = scord_units * yields["Scordite"]["Tritanium"]

        self.assertLess(zeolite_m3, scord_m3)
        self.assertGreater(trit_overage, 100_000_000)
        self.assertNotIn("Scordite", belt)

    def test_plagioclase_beats_kernite_volume_for_mex_only(self):
        refine = 0.84
        yields = _standard_yields(refine)
        needs = {"Mexallon": 100_000_000}
        belt, _ = compute_practical_belt_blend(needs, {}, yields)
        plag_m3 = belt_ore_compressed_volume_m3(belt)

        kern_units = needs["Mexallon"] / yields["Kernite"]["Mexallon"]
        kern_m3 = belt_ore_compressed_volume_m3({"Kernite": kern_units})
        iso_overage = kern_units * yields["Kernite"]["Isogen"]

        self.assertLess(plag_m3, kern_m3)
        self.assertGreater(iso_overage, 100_000_000)
        self.assertNotIn("Kernite", belt)
        self.assertIn("Plagioclase", belt)

    def test_scordite_fallback_when_zeolites_unavailable(self):
        refine = 0.84
        yields = {
            "Veldspar": {"Tritanium": 4.0 * refine},
            "Scordite": {"Tritanium": 1.5 * refine, "Pyerite": 0.99 * refine},
            "Plagioclase": {
                "Tritanium": 1.75 * refine,
                "Mexallon": 0.7 * refine,
            },
        }
        belt, _ = compute_practical_belt_blend(
            {"Pyerite": 1_000_000, "Tritanium": 2_000_000}, {}, yields
        )
        self.assertIn("Scordite", belt)
        self.assertIn("Veldspar", belt)
        self.assertNotIn("Zeolites", belt)

    def test_kernite_fallback_when_plagioclase_unavailable(self):
        refine = 0.84
        yields = {
            "Veldspar": {"Tritanium": 4.0 * refine},
            "Zeolites": {"Pyerite": 80.0 * refine, "Mexallon": 4.0 * refine},
            "Kernite": {"Mexallon": 0.6 * refine, "Isogen": 1.2 * refine},
        }
        belt, imports = compute_practical_belt_blend(
            {"Mexallon": 600_000}, {}, yields
        )
        self.assertIn("Kernite", belt)
        self.assertNotIn("Plagioclase", belt)
        self.assertNotIn("Zeolites", belt)  # never size Pye ore for Mex-only
        self.assertEqual(imports.get("Mexallon", 0), 0)


class BeltOreBlendTestCase(TestCase):
    def test_practical_blend_covers_only_allowlisted_minerals(self):
        mineral_needs = {
            "Tritanium": 8_000_000,
            "Pyerite": 4_000_000,
            "Mexallon": 600_000,
            "Isogen": 400_000,
            "Nocxium": 30_000,
            "Zydrine": 8_000,
            "Megacyte": 4_000,
        }
        moon_byproducts = {"Pyerite": 0, "Mexallon": 0}
        refine = 0.84
        ore_yields = _standard_yields(refine)
        belt_units, mineral_imports = compute_practical_belt_blend(
            mineral_needs, moon_byproducts, ore_yields
        )
        self.assertIn("Zeolites", belt_units)
        self.assertIn("Plagioclase", belt_units)
        self.assertIn("Veldspar", belt_units)
        self.assertNotIn("Scordite", belt_units)
        self.assertNotIn("Kernite", belt_units)
        for covered in COMPRESSION_COVERED_MINERALS:
            self.assertEqual(mineral_imports.get(covered, 0), 0)
        # Isogen / rares stay as imports (Kernite not used when Plagioclase available).
        self.assertEqual(mineral_imports["Isogen"], 400_000)
        self.assertEqual(mineral_imports["Nocxium"], 30_000)
        compressed = to_compressed_units(belt_units)
        self.assertGreater(compressed["Compressed Zeolites"], 50_000)
        self.assertGreater(compressed["Compressed Plagioclase"], 100_000)
        self.assertGreater(compressed["Compressed Veldspar"], 1_500_000)


class CompressionAllowlistTestCase(TestCase):
    def test_covered_materials_include_minerals_and_ice(self):
        covered = compression_covered_materials()
        self.assertEqual(
            [m for m in covered if m in COMPRESSION_COVERED_MINERALS],
            ["Mexallon", "Pyerite", "Tritanium"],
        )
        self.assertIn("Heavy Water", covered)
        self.assertIn("Liquid Ozone", covered)
        self.assertIn("Strontium Clathrates", covered)
        self.assertNotIn("Helium Isotopes", covered)
        self.assertEqual(
            COMPRESSION_COVERED_MINERALS,
            frozenset({"Tritanium", "Pyerite", "Mexallon"}),
        )

    @patch("industry.helpers.compressed_ore.base_belt_ore_yields")
    def test_isogen_stays_as_mineral_import_mex_compressed(self, mock_yields):
        refine = 0.84
        mock_yields.return_value = _standard_yields(refine)
        plan = build_compressed_ore_plan(
            {
                "Tritanium": 1_000_000,
                "Pyerite": 500_000,
                "Mexallon": 100_000,
                "Isogen": 50_000,
            },
            refine_rate=refine,
            use_moon_ore=False,
            require_market=False,
        )
        names = {name for name, _ in plan.import_lines()}
        self.assertNotIn("Tritanium", names)
        self.assertNotIn("Pyerite", names)
        self.assertNotIn("Mexallon", names)
        self.assertIn("Isogen", names)
        self.assertIn("Compressed Zeolites", plan.belt_ore_compressed)
        self.assertIn("Compressed Plagioclase", plan.belt_ore_compressed)
        self.assertIn("Compressed Veldspar", plan.belt_ore_compressed)
        self.assertNotIn("Compressed Scordite", plan.belt_ore_compressed)
        self.assertNotIn("Compressed Kernite", plan.belt_ore_compressed)
        self.assertEqual(plan.mineral_imports["Isogen"], 50_000)


class CompressedOrePlanTestCase(TestCase):
    @patch("industry.helpers.compressed_ore.base_belt_ore_yields")
    def test_build_plan_splits_belt_and_imports(self, mock_yields):
        refine = 0.84
        mock_yields.return_value = _standard_yields(refine)
        buckets = MaterialBuckets(
            minerals={
                "Tritanium": 8_000_000,
                "Pyerite": 4_000_000,
                "Mexallon": 600_000,
                "Isogen": 400_000,
                "Nocxium": 30_000,
                "Zydrine": 8_000,
                "Megacyte": 4_000,
            },
            pi_p0={
                "Hydrocarbons": 9200,
                "Atmospheric Gases": 9200,
                "Evaporite Deposits": 1200,
                "Silicates": 1200,
            },
            pi_other={"Mechanical Parts": 48},
            ice={"Liquid Ozone": 1000},
        )
        plan = build_compressed_ore_plan(
            buckets,
            refine_rate=0.84,
            use_moon_ore=True,
            require_market=False,
        )
        # PI P0 is not on the compression allowlist yet → direct imports.
        self.assertFalse(plan.moon_ore_compressed)
        self.assertEqual(plan.other_imports["Hydrocarbons"], 9200)
        self.assertTrue(plan.belt_ore_compressed)
        self.assertEqual(plan.mineral_imports["Nocxium"], 30_000)
        self.assertEqual(plan.mineral_imports["Isogen"], 400_000)
        self.assertEqual(plan.pi_other_imports["Mechanical Parts"], 48)
        # Liquid Ozone is covered by Compressed Dark Glitter.
        self.assertIn("Compressed Dark Glitter", plan.ice_compressed)
        self.assertNotIn("Liquid Ozone", plan.ice_imports)
        names = {name for name, _ in plan.import_lines()}
        self.assertNotIn("Compressed Bitumens", names)
        self.assertIn("Compressed Zeolites", names)
        self.assertIn("Compressed Plagioclase", names)
        self.assertIn("Compressed Veldspar", names)
        self.assertIn("Compressed Dark Glitter", names)
        self.assertNotIn("Compressed Scordite", names)
        self.assertNotIn("Mexallon", names)
        self.assertIn("Nocxium", names)
        self.assertIn("Hydrocarbons", names)
        self.assertNotIn("Tritanium", names)
        self.assertEqual(plan.reprocessing_tax, 0.0)
        self.assertIn("Tritanium", plan.expected_minerals)
        self.assertIn("Liquid Ozone", plan.expected_ice_products)
        self.assertGreaterEqual(
            plan.expected_minerals["Tritanium"]
            + plan.mineral_imports.get("Tritanium", 0),
            plan.mineral_needs["Tritanium"],
        )

    def test_reprocessing_tax_on_plan(self):
        plan = build_compressed_ore_plan(
            {"Tritanium": 1000},
            refine_rate=0.84,
            use_moon_ore=False,
            reprocessing_tax=0.025,
            require_market=False,
        )
        self.assertTrue(plan.includes_compressed_ore)
        self.assertAlmostEqual(plan.reprocessing_tax, 0.025)
        self.assertEqual(plan.tax_isk(5060.0), 126)

        refined_only = build_compressed_ore_plan(
            {"Nocxium": 30_000},
            refine_rate=0.84,
            use_moon_ore=False,
            reprocessing_tax=0.025,
            require_market=False,
        )
        self.assertFalse(refined_only.includes_compressed_ore)
        self.assertEqual(refined_only.reprocessing_tax, 0.0)
        self.assertEqual(refined_only.tax_isk(1_000_000.0), 0)

    def test_fallback_yields_never_emit_trit(self):
        plan = build_compressed_ore_plan(
            {"Tritanium": 8_000_000, "Nocxium": 30_000},
            refine_rate=0.84,
            use_moon_ore=False,
            require_market=False,
        )
        names = {name for name, _ in plan.import_lines()}
        self.assertNotIn("Tritanium", names)
        self.assertIn("Compressed Veldspar", names)
        self.assertNotIn("Compressed Scordite", names)
        self.assertNotIn("Compressed Zeolites", names)
        # 1:1 compression: ~8e6 / (4*0.84) ≈ 2.38e6 Compressed Veldspar
        self.assertGreater(
            plan.belt_ore_compressed["Compressed Veldspar"], 2_000_000
        )

    def test_to_compressed_units_is_one_to_one(self):
        compressed = to_compressed_units({"Zeolites": 59_524})
        self.assertEqual(compressed["Compressed Zeolites"], 59_524)

    def test_reprocess_output_portion_math(self):
        # 100 Veldspar @ 84% → floor(100/100 * 400 * 0.84) = 336 Trit
        out = reprocess_output("Veldspar", 100, refine_rate=0.84)
        self.assertEqual(out["Tritanium"], 336)

    def test_floor_top_up_eliminates_covered_mineral_shortfall(self):
        """Continuous blend can undershoot Trit by 1; top-up closes the gap."""
        plan = build_compressed_ore_plan(
            {
                "Tritanium": 8_000_001,
                "Pyerite": 4_000_000,
                "Mexallon": 600_001,
            },
            refine_rate=0.84,
            use_moon_ore=False,
            require_market=False,
        )
        for mineral in COMPRESSION_COVERED_MINERALS:
            self.assertGreaterEqual(
                plan.mineral_delta.get(mineral, 0),
                0,
                msg=f"{mineral} delta={plan.mineral_delta.get(mineral)}",
            )
            self.assertGreaterEqual(
                plan.expected_minerals.get(mineral, 0)
                + plan.mineral_imports.get(mineral, 0),
                plan.mineral_needs.get(mineral, 0),
            )

    def test_conservative_refine_rate_matches_ui_percent(self):
        full = get_facility_refine_rate("amamake", implant=0.04)
        self.assertAlmostEqual(full, 0.8577302848, places=7)
        # UI: (full * 100).toFixed(2) → 85.77%
        self.assertEqual(conservative_refine_rate(full), 0.8577)
        # Never round above the true rate.
        self.assertEqual(conservative_refine_rate(0.85775), 0.85775)
        self.assertEqual(conservative_refine_rate(0.84), 0.84)

    def test_top_up_covers_at_display_refine_rate(self):
        """
        Amamake+RX804 plans must still cover Trit/Pye/Mex when refined at the
        UI/Janice 2-decimal percent (85.77%), not only at full float precision.
        """
        full = get_facility_refine_rate("amamake", implant=0.04)
        display = conservative_refine_rate(full)
        # Typhoon Fleet Issue ×40 mineral leaves (ME 0) — Discord / Order #38.
        needs = {
            "Tritanium": 304_761_600,
            "Pyerite": 152_380_800,
            "Mexallon": 22_857_120,
            "Isogen": 15_238_080,
            "Nocxium": 1_142_856,
            "Zydrine": 304_762,
            "Megacyte": 152_381,
        }
        plan = build_compressed_ore_plan(
            needs,
            refine_rate=full,
            use_moon_ore=False,
            require_market=False,
        )
        expected_at_display: dict[str, int] = {}
        for ore_name, qty in plan.belt_ore_compressed.items():
            for mat, produced in reprocess_output(
                base_ore_name(ore_name), qty, refine_rate=display
            ).items():
                expected_at_display[mat] = (
                    expected_at_display.get(mat, 0) + produced
                )
        for mineral in COMPRESSION_COVERED_MINERALS:
            got = expected_at_display.get(
                mineral, 0
            ) + plan.mineral_imports.get(mineral, 0)
            self.assertGreaterEqual(
                got,
                needs[mineral],
                msg=(
                    f"{mineral}: display refine {display} produced {got}, "
                    f"need {needs[mineral]}"
                ),
            )
        # Slight overage vs the pre-fix exact stacks from continuous sizing.
        self.assertGreater(
            plan.belt_ore_compressed["Compressed Veldspar"], 77_724_433
        )
        self.assertGreater(
            plan.belt_ore_compressed["Compressed Zeolites"], 2_220_699
        )
        self.assertGreater(
            plan.belt_ore_compressed["Compressed Plagioclase"], 25_379_407
        )

    def test_covered_minerals_never_negative_delta(self):
        plan = build_compressed_ore_plan(
            {
                "Tritanium": 8_000_000,
                "Pyerite": 4_000_000,
                "Mexallon": 600_000,
                "Nocxium": 30_000,
            },
            refine_rate=0.84,
            use_moon_ore=False,
            require_market=False,
        )
        for mineral in COMPRESSION_COVERED_MINERALS:
            self.assertGreaterEqual(
                plan.expected_minerals.get(mineral, 0)
                + plan.mineral_imports.get(mineral, 0),
                plan.mineral_needs.get(mineral, 0),
            )

    def test_lower_refine_needs_more_ore(self):
        mats = {"Tritanium": 4_000_000, "Pyerite": 1_000_000}
        with patch(
            "industry.helpers.compressed_ore.base_belt_ore_yields"
        ) as mock_y:

            def yields(refine_rate, require_market=True):
                return _standard_yields(refine_rate)

            mock_y.side_effect = yields
            hi = build_compressed_ore_plan(
                mats, refine_rate=0.90, require_market=False
            )
            lo = build_compressed_ore_plan(
                mats, refine_rate=0.70, require_market=False
            )
        self.assertGreater(
            lo.belt_ore_compressed.get("Compressed Zeolites", 0),
            hi.belt_ore_compressed.get("Compressed Zeolites", 0),
        )
        self.assertGreater(
            lo.belt_ore_compressed.get("Compressed Veldspar", 0),
            hi.belt_ore_compressed.get("Compressed Veldspar", 0),
        )

    def test_implant_refine_reduces_compressed_ore_qty(self):
        """Implant toggle ON raises refine yield and needs less compressed ore."""
        mats = {"Tritanium": 4_000_000, "Pyerite": 1_000_000}
        char = EveCharacter.objects.create(
            character_id=2122000099,
            character_name="Ore Implant Pilot",
            active_implants=[27174],
        )
        for sid, level, name in (
            (3385, 5, "Reprocessing"),
            (3389, 5, "Reprocessing Efficiency"),
            (60377, 5, "Simple Ore Processing"),
            (60378, 5, "Coherent Ore Processing"),
            (46152, 5, "Ubiquitous Moon Ore Processing"),
        ):
            EveCharacterSkill.objects.create(
                character=char,
                skill_id=sid,
                skill_name=name,
                skill_points=level * 1000,
                skill_level=level,
            )

        rate_without, _, _ = resolve_refine_rate(
            "amamake",
            character=char,
            use_reprocessing_implants=False,
        )
        rate_with, _, skills = resolve_refine_rate(
            "amamake",
            character=char,
            use_reprocessing_implants=True,
        )
        self.assertAlmostEqual(skills.effective_implant, 0.04)
        self.assertGreater(rate_with, rate_without)
        self.assertAlmostEqual(rate_without, 0.8247406585, places=7)
        self.assertAlmostEqual(rate_with, 0.8577302848, places=7)

        with patch(
            "industry.helpers.compressed_ore.base_belt_ore_yields"
        ) as mock_y:

            def yields(refine_rate, require_market=True):
                return _standard_yields(refine_rate)

            mock_y.side_effect = yields
            plan_without = build_compressed_ore_plan(
                mats, refine_rate=rate_without, require_market=False
            )
            plan_with = build_compressed_ore_plan(
                mats, refine_rate=rate_with, require_market=False
            )

        qty_without = plan_without.belt_ore_compressed.get(
            "Compressed Zeolites", 0
        )
        qty_with = plan_with.belt_ore_compressed.get("Compressed Zeolites", 0)
        self.assertGreater(qty_without, qty_with)
        self.assertAlmostEqual(plan_with.refine_rate, rate_with, places=10)


def _standard_ice_yields(refine: float = 0.84) -> dict:
    """Per-unit ice yields at refine_rate (portion size 1)."""
    return {
        "Glare Crust": {
            "Heavy Water": 1381 * refine,
            "Liquid Ozone": 691 * refine,
            "Strontium Clathrates": 35 * refine,
        },
        "Dark Glitter": {
            "Heavy Water": 691 * refine,
            "Liquid Ozone": 1381 * refine,
            "Strontium Clathrates": 69 * refine,
        },
        "Gelidus": {
            "Heavy Water": 345 * refine,
            "Liquid Ozone": 691 * refine,
            "Strontium Clathrates": 104 * refine,
        },
        "Krystallos": {
            "Heavy Water": 173 * refine,
            "Liquid Ozone": 691 * refine,
            "Strontium Clathrates": 173 * refine,
        },
    }


class CompressedIcePlanTestCase(TestCase):
    @patch("industry.helpers.compressed_ore.base_compression_ice_yields")
    def test_helium_fuel_compresses_hw_lo_sr_not_isotopes(self, mock_yields):
        refine = 0.84
        mock_yields.return_value = _standard_ice_yields(refine)
        # Rough Helium Fuel Block leaf ratio (ME-adjusted-ish).
        plan = build_compressed_ore_plan(
            {
                "Heavy Water": 146_000,
                "Liquid Ozone": 300_000,
                "Helium Isotopes": 386_000,
                "Strontium Clathrates": 18_000,
            },
            refine_rate=refine,
            require_market=False,
        )
        self.assertTrue(plan.includes_compressed_ore)
        # Isotopes stay as direct imports (tiny m3).
        self.assertEqual(plan.ice_imports["Helium Isotopes"], 386_000)
        self.assertNotIn("Compressed Clear Icicle", plan.ice_compressed)
        names = {name for name, _ in plan.import_lines()}
        self.assertIn("Helium Isotopes", names)
        self.assertIn("Compressed Glare Crust", names)
        self.assertIn("Compressed Dark Glitter", names)
        self.assertIn("Compressed Krystallos", names)
        expected = plan.expected_ice_products
        self.assertGreaterEqual(
            expected.get("Heavy Water", 0)
            + plan.ice_imports.get("Heavy Water", 0),
            146_000,
        )
        self.assertGreaterEqual(
            expected.get("Liquid Ozone", 0)
            + plan.ice_imports.get("Liquid Ozone", 0),
            300_000,
        )
        self.assertGreaterEqual(
            expected.get("Strontium Clathrates", 0)
            + plan.ice_imports.get("Strontium Clathrates", 0),
            18_000,
        )

    @patch("industry.helpers.compressed_ore.base_compression_ice_yields")
    def test_liquid_ozone_only_uses_dark_glitter(self, mock_yields):
        refine = 0.84
        mock_yields.return_value = _standard_ice_yields(refine)
        plan = build_compressed_ore_plan(
            {"Liquid Ozone": 1000},
            refine_rate=refine,
            require_market=False,
        )
        self.assertIn("Compressed Dark Glitter", plan.ice_compressed)
        self.assertNotIn("Liquid Ozone", plan.ice_imports)
        self.assertGreaterEqual(
            plan.expected_ice_products.get("Liquid Ozone", 0), 1000
        )

    def test_compression_covered_includes_ice(self):
        covered = compression_covered_materials()
        self.assertIn("Heavy Water", covered)
        self.assertIn("Liquid Ozone", covered)
        self.assertIn("Strontium Clathrates", covered)
        self.assertNotIn("Helium Isotopes", covered)
        self.assertIn("Tritanium", covered)
