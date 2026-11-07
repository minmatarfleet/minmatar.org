"""Invention (T2/T3) in the industry planner: maths, SDE loader, plans, API."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import Client, SimpleTestCase, TestCase
from eveuniverse.models import (
    EveCategory,
    EveGroup,
    EveIndustryActivity,
    EveIndustryActivityDuration,
    EveIndustryActivityMaterial,
    EveIndustryActivityProduct,
    EveMarketPrice,
    EveType,
)

from industry.helpers.build_planner import RootBlueprint, plan_build
from industry.helpers.facility_profiles import AMAMAKE_SYSTEM_ID, JobClass
from industry.helpers.invention import (
    NO_DECRYPTOR,
    AttemptInput,
    DecryptorOption,
    FeeParts,
    InventionSkills,
    SourceOption,
    attempts_for_confidence,
    choose,
    quote,
    success_chance,
)
from industry.helpers.invention_planner import (
    InventionRequest,
    invention_to_dict,
    plan_invented_build,
    quote_invention,
)
from industry.helpers.invention_sde import extract, load_from_path
from industry.helpers.plan_costing import (
    PlanCostOptions,
    cost_build_plan,
    plan_item_cost,
)
from industry.models import (
    IndustryProduct,
    IndustrySystemCostIndex,
    InventionDecryptor,
    InventionOutcome,
)

ACCELERANT = DecryptorOption(
    type_id=34201,
    name="Accelerant Decryptor",
    probability_multiplier=1.2,
    runs_modifier=1,
    me_modifier=2,
    te_modifier=10,
    unit_price=300_000,
)
OPT_AUGMENTATION = DecryptorOption(
    type_id=34208,
    name="Optimized Augmentation Decryptor",
    probability_multiplier=0.9,
    runs_modifier=7,
    me_modifier=2,
    te_modifier=0,
    unit_price=4_000_000,
)
# Worse than no decryptor in every way and not free: must never win.
DOMINATED = DecryptorOption(
    type_id=1,
    name="Dominated Decryptor",
    probability_multiplier=0.5,
    runs_modifier=0,
    me_modifier=-2,
    te_modifier=0,
    unit_price=1_000_000,
)


def _hac_source(base_runs=1, probability=0.26) -> SourceOption:
    return SourceOption(
        source_type_id=1,
        source_name="Rupture Blueprint",
        source_kind=InventionOutcome.SOURCE_T1_BLUEPRINT,
        base_probability=probability,
        base_runs=base_runs,
        inputs=(
            AttemptInput(1, "Datacore A", 8, 100_000),
            AttemptInput(2, "Datacore B", 8, 100_000),
        ),
        invention_fee=FeeParts(gross=100_000, facility_tax=10_000, scc=20_000),
        copy_fee=FeeParts(gross=1_000),
        invention_seconds=100.0,
        copy_seconds=10.0,
    )


class InventionMathsTests(SimpleTestCase):
    def test_success_chance_matches_the_sde_formula(self):
        # Muninn: base 26%, Science V/V, Encryption IV, Accelerant x1.2.
        self.assertAlmostEqual(
            success_chance(0.26, InventionSkills(), 1.2),
            0.26 * (1 + 10 / 30 + 4 / 40) * 1.2,
        )
        self.assertAlmostEqual(
            success_chance(0.26, InventionSkills(), 1.2), 0.4472, places=4
        )
        # Wrecked relic + Optimized Augmentation: the research model's 0.18.
        self.assertAlmostEqual(
            success_chance(0.14, InventionSkills(), 0.9), 0.1806, places=4
        )

    def test_success_chance_is_capped_at_one(self):
        self.assertEqual(success_chance(0.9, InventionSkills(), 1.9), 1.0)

    def test_attempts_for_confidence(self):
        # One success at 50%: 1 - 0.5^n >= 0.9 first holds at n = 4.
        self.assertEqual(attempts_for_confidence(1, 0.5), 4)
        self.assertEqual(attempts_for_confidence(3, 1.0), 3)
        self.assertEqual(attempts_for_confidence(0, 0.4), 0)
        big = attempts_for_confidence(1000, 0.5)
        self.assertGreater(big, 2000)
        self.assertLess(big, 2200)

    def test_quote_amortises_copy_runs_and_rounds_the_buy_list(self):
        q = quote(
            source=_hac_source(base_runs=10, probability=0.34),
            decryptor=NO_DECRYPTOR,
            skills=InventionSkills(),
            units=1,
            products_per_run=1,
            build_cost=lambda me, runs: 0.0,
        )
        chance = 0.34 * (1 + 10 / 30 + 4 / 40)
        self.assertEqual(q.runs_per_copy, 10)
        self.assertEqual((q.copy_me, q.copy_te), (2, 4))
        self.assertAlmostEqual(q.copies_needed, 0.1)
        self.assertAlmostEqual(q.expected_attempts, 0.1 / chance)
        # One whole copy has to be invented before the first unit.
        self.assertEqual(q.buy_attempts, 3)
        per_attempt = 16 * 100_000 + 130_000 + 1_000
        self.assertAlmostEqual(q.attempt_isk, per_attempt)
        self.assertAlmostEqual(q.invention_isk, per_attempt * 0.1 / chance)

    def test_runs_and_me_win_when_the_build_is_expensive(self):
        # 100M of materials at ME0: each ME point saves about 1M per unit.
        def build_cost(me, runs):
            return 100_000_000 * (1 - me)

        choice = choose(
            sources=[_hac_source()],
            decryptors=[NO_DECRYPTOR, ACCELERANT, OPT_AUGMENTATION, DOMINATED],
            skills=InventionSkills(),
            units=1,
            products_per_run=1,
            build_cost=build_cost,
        )
        self.assertIn(choice.best.decryptor.type_id, (34201, 34208))
        self.assertNotEqual(choice.best.decryptor.type_id, DOMINATED.type_id)

    def test_no_decryptor_wins_when_the_build_is_cheap(self):
        choice = choose(
            sources=[_hac_source(base_runs=10, probability=0.34)],
            decryptors=[NO_DECRYPTOR, OPT_AUGMENTATION, DOMINATED],
            skills=InventionSkills(),
            units=10,
            products_per_run=1,
            build_cost=lambda me, runs: 1_000.0,
        )
        self.assertIsNone(choice.best.decryptor.type_id)
        self.assertEqual(
            choice.alternatives[-1].decryptor.name, DOMINATED.name
        )

    def test_expected_attempts_times_chance_is_copies_needed(self):
        for decryptor in (NO_DECRYPTOR, ACCELERANT, OPT_AUGMENTATION):
            q = quote(
                source=_hac_source(),
                decryptor=decryptor,
                skills=InventionSkills(),
                units=7,
                products_per_run=1,
                build_cost=lambda me, runs: 0.0,
            )
            self.assertAlmostEqual(
                q.expected_attempts * q.chance, q.copies_needed
            )


def _write_jsonl(directory: Path, name: str, rows):
    with open(directory / f"{name}.jsonl", "w", encoding="utf8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


class InventionSdeLoaderTests(TestCase):
    def _sde_dir(self, directory: Path):
        _write_jsonl(directory, "_sde", [{"_key": "sde", "buildNumber": 42}])
        _write_jsonl(
            directory,
            "groups",
            [
                {"_key": 105, "categoryID": 9},  # Cruiser Blueprint
                {"_key": 971, "categoryID": 34},  # Sleeper Hull Relics
                {"_key": 26, "categoryID": 6},
                {"_key": 358, "categoryID": 6},
                {"_key": 963, "categoryID": 6},
                {"_key": 270, "categoryID": 16},
                {"_key": 1304, "categoryID": 35},
            ],
        )
        _write_jsonl(
            directory,
            "types",
            [
                {
                    "_key": 11,
                    "groupID": 105,
                    "name": {"en": "Rupture Blueprint"},
                    "published": True,
                },
                {
                    "_key": 12,
                    "groupID": 26,
                    "name": {"en": "Rupture"},
                    "published": True,
                },
                {
                    "_key": 13,
                    "groupID": 105,
                    "name": {"en": "Muninn Blueprint"},
                    "published": True,
                },
                {
                    "_key": 14,
                    "groupID": 358,
                    "name": {"en": "Muninn"},
                    "published": True,
                },
                {
                    "_key": 21,
                    "groupID": 971,
                    "name": {"en": "Wrecked Hull Section"},
                    "published": True,
                },
                {
                    "_key": 22,
                    "groupID": 105,
                    "name": {"en": "Loki Blueprint"},
                    "published": True,
                },
                {
                    "_key": 23,
                    "groupID": 963,
                    "name": {"en": "Loki"},
                    "published": True,
                },
                {
                    "_key": 31,
                    "groupID": 270,
                    "name": {"en": "Minmatar Encryption Methods"},
                    "published": True,
                },
                {
                    "_key": 32,
                    "groupID": 270,
                    "name": {"en": "Mechanical Engineering"},
                    "published": True,
                },
                {
                    "_key": 41,
                    "groupID": 1304,
                    "name": {"en": "Accelerant Decryptor"},
                    "published": True,
                },
            ],
        )
        _write_jsonl(
            directory,
            "blueprints",
            [
                {
                    "_key": 11,
                    "activities": {
                        "copying": {"time": 4800},
                        "invention": {
                            "materials": [{"typeID": 99, "quantity": 8}],
                            "products": [
                                {
                                    "typeID": 13,
                                    "probability": 0.26,
                                    "quantity": 1,
                                }
                            ],
                            "skills": [
                                {"typeID": 31, "level": 1},
                                {"typeID": 32, "level": 1},
                            ],
                            "time": 128100,
                        },
                        "manufacturing": {
                            "products": [{"typeID": 12, "quantity": 1}]
                        },
                    },
                },
                {
                    "_key": 13,
                    "activities": {
                        "manufacturing": {
                            "products": [{"typeID": 14, "quantity": 1}]
                        }
                    },
                },
                {
                    "_key": 21,
                    "activities": {
                        "invention": {
                            "materials": [{"typeID": 98, "quantity": 3}],
                            "products": [
                                {
                                    "typeID": 22,
                                    "probability": 0.14,
                                    "quantity": 3,
                                }
                            ],
                            "time": 3600,
                        }
                    },
                },
                {
                    "_key": 22,
                    "activities": {
                        "manufacturing": {
                            "products": [{"typeID": 23, "quantity": 1}]
                        }
                    },
                },
            ],
        )
        _write_jsonl(
            directory,
            "typeDogma",
            [
                {
                    "_key": 41,
                    "dogmaAttributes": [
                        {"attributeID": 1112, "value": 1.2},
                        {"attributeID": 1113, "value": 2.0},
                        {"attributeID": 1114, "value": 10.0},
                        {"attributeID": 1124, "value": 1.0},
                    ],
                }
            ],
        )

    def test_extract_reads_t2_and_t3_outcomes_and_decryptors(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self._sde_dir(directory)
            build, outcomes, decryptors = extract(directory)
        self.assertEqual(build, 42)
        by_product = {row["product_type_id"]: row for row in outcomes}
        muninn = by_product[14]
        self.assertEqual(
            muninn["source_kind"], InventionOutcome.SOURCE_T1_BLUEPRINT
        )
        self.assertEqual(muninn["source_product_type_id"], 12)
        self.assertEqual(muninn["copy_time_seconds"], 4800)
        self.assertEqual(muninn["encryption_skill_id"], 31)
        self.assertEqual(muninn["science_skill_ids"], [32])
        self.assertAlmostEqual(muninn["probability"], 0.26)
        loki = by_product[23]
        self.assertEqual(loki["source_kind"], InventionOutcome.SOURCE_RELIC)
        self.assertEqual(loki["runs"], 3)
        self.assertIsNone(loki["source_product_type_id"])
        self.assertEqual(
            decryptors,
            [
                {
                    "type_id": 41,
                    "name": "Accelerant Decryptor",
                    "probability_multiplier": 1.2,
                    "runs_modifier": 1,
                    "me_modifier": 2,
                    "te_modifier": 10,
                    "sde_build": 42,
                }
            ],
        )

    def test_load_replaces_rows(self):
        InventionOutcome.objects.create(
            source_type_id=500,
            source_kind=InventionOutcome.SOURCE_T1_BLUEPRINT,
            blueprint_type_id=501,
            product_type_id=502,
            probability=0.5,
            runs=1,
            time_seconds=1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self._sde_dir(directory)
            build, n_outcomes, n_decryptors = load_from_path(directory)
        self.assertEqual((build, n_outcomes, n_decryptors), (42, 2, 1))
        self.assertFalse(
            InventionOutcome.objects.filter(product_type_id=502).exists()
        )
        self.assertEqual(
            InventionDecryptor.objects.get().name, "Accelerant Decryptor"
        )


# Toy HAC tree: Toy Cruiser (T1 hull) + 100 Toy Plates → Toy HAC.
TRIT = 34
CRUISER, HAC, PLATE, MODULE = 910001, 910002, 910003, 910004
CRUISER_BP, HAC_BP, PLATE_BP, MODULE_BP = 910011, 910012, 910013, 910014
DATACORE_A, DATACORE_B = 910021, 910022

JITA = {
    TRIT: 4,
    CRUISER: 11_000_000,
    PLATE: 40_000,
    DATACORE_A: 100_000,
    DATACORE_B: 100_000,
    34201: 300_000,
    34208: 4_000_000,
}


def _jita(type_ids):
    return {tid: JITA[tid] for tid in type_ids if tid in JITA}


class ToyHacFixture(TestCase):
    @classmethod
    def setUpTestData(cls):  # pylint: disable=invalid-name
        ship, _ = EveCategory.objects.get_or_create(
            id=6, defaults={"name": "Ship", "published": True}
        )
        module_cat, _ = EveCategory.objects.get_or_create(
            id=7, defaults={"name": "Module", "published": True}
        )
        commodity, _ = EveCategory.objects.get_or_create(
            id=17, defaults={"name": "Commodity", "published": True}
        )
        material, _ = EveCategory.objects.get_or_create(
            id=4, defaults={"name": "Material", "published": True}
        )
        cruiser_g, _ = EveGroup.objects.get_or_create(
            id=26,
            defaults={
                "name": "Cruiser",
                "published": True,
                "eve_category": ship,
            },
        )
        hac_g, _ = EveGroup.objects.get_or_create(
            id=358,
            defaults={
                "name": "Heavy Assault Cruiser",
                "published": True,
                "eve_category": ship,
            },
        )
        comp_g, _ = EveGroup.objects.get_or_create(
            id=334,
            defaults={
                "name": "Construction Components",
                "published": True,
                "eve_category": commodity,
            },
        )
        mineral_g, _ = EveGroup.objects.get_or_create(
            id=18,
            defaults={
                "name": "Mineral",
                "published": True,
                "eve_category": material,
            },
        )
        module_g, _ = EveGroup.objects.get_or_create(
            id=59,
            defaults={
                "name": "Gyrostabilizer",
                "published": True,
                "eve_category": module_cat,
            },
        )
        EveIndustryActivity.objects.get_or_create(
            id=1, defaults={"name": "Manufacturing", "description": "m"}
        )
        EveType.objects.get_or_create(
            id=TRIT,
            defaults={
                "name": "Tritanium",
                "published": True,
                "eve_group": mineral_g,
            },
        )
        types = {
            CRUISER: ("Toy Cruiser", cruiser_g),
            HAC: ("Toy HAC", hac_g),
            PLATE: ("Toy Plate", comp_g),
            MODULE: ("Toy Gyro", module_g),
            CRUISER_BP: ("Toy Cruiser Blueprint", mineral_g),
            HAC_BP: ("Toy HAC Blueprint", mineral_g),
            PLATE_BP: ("Toy Plate Blueprint", mineral_g),
            MODULE_BP: ("Toy Gyro Blueprint", mineral_g),
            DATACORE_A: ("Datacore - Toy A", comp_g),
            DATACORE_B: ("Datacore - Toy B", comp_g),
        }
        for tid, (name, group) in types.items():
            EveType.objects.create(
                id=tid, name=name, published=True, eve_group=group
            )

        def recipe(bp, product, time, materials):
            EveIndustryActivityProduct.objects.create(
                eve_type_id=bp,
                activity_id=1,
                product_eve_type_id=product,
                quantity=1,
            )
            EveIndustryActivityDuration.objects.create(
                eve_type_id=bp, activity_id=1, time=time
            )
            for mid, qty in materials:
                EveIndustryActivityMaterial.objects.create(
                    eve_type_id=bp,
                    activity_id=1,
                    material_eve_type_id=mid,
                    quantity=qty,
                )

        recipe(CRUISER_BP, CRUISER, 6000, [(TRIT, 1_000_000)])
        recipe(PLATE_BP, PLATE, 300, [(TRIT, 5_000)])
        recipe(HAC_BP, HAC, 240_000, [(CRUISER, 1), (PLATE, 100)])
        recipe(MODULE_BP, MODULE, 600, [(TRIT, 50_000)])

        for tid, adjusted in (
            (TRIT, 5.0),
            (CRUISER, 10_000_000.0),
            (PLATE, 30_000.0),
        ):
            EveMarketPrice.objects.create(
                eve_type_id=tid,
                adjusted_price=adjusted,
                average_price=adjusted,
            )
        IndustrySystemCostIndex.objects.create(
            solar_system_id=AMAMAKE_SYSTEM_ID,
            manufacturing=0.10,
            reaction=0.10,
            invention=0.10,
            copying=0.10,
        )
        InventionOutcome.objects.create(
            source_type_id=CRUISER_BP,
            source_name="Toy Cruiser Blueprint",
            source_kind=InventionOutcome.SOURCE_T1_BLUEPRINT,
            source_product_type_id=CRUISER,
            copy_time_seconds=4800,
            blueprint_type_id=HAC_BP,
            product_type_id=HAC,
            probability=0.26,
            runs=1,
            time_seconds=128_100,
            materials=[[DATACORE_A, 8], [DATACORE_B, 8]],
        )
        for row in (ACCELERANT, OPT_AUGMENTATION):
            InventionDecryptor.objects.create(
                type_id=row.type_id,
                name=row.name,
                probability_multiplier=row.probability_multiplier,
                runs_modifier=row.runs_modifier,
                me_modifier=row.me_modifier,
                te_modifier=row.te_modifier,
            )

    def setUp(self):
        for target in (
            "industry.helpers.invention_planner.jita_sell_unit_prices_by_type_id",
            "industry.helpers.plan_costing.materials_jita_sell_isk_from_type_qtys",
            "industry.helpers.plan_costing.jita_sell_prices_by_type_id",
        ):
            patcher = patch(target)
            mock = patcher.start()
            self.addCleanup(patcher.stop)
            if target.endswith("from_type_qtys"):
                mock.side_effect = lambda qtys, **_: sum(
                    qty * JITA.get(tid, 0) for tid, qty in qtys
                )
            else:
                mock.side_effect = _jita


class InventedPlanTests(ToyHacFixture):
    def test_quote_prices_fees_on_two_percent_of_the_product_eiv(self):
        choice = quote_invention(HAC, 1, "amamake")
        source = choice.best.source
        # EIV of one Toy HAC run: 10M hull + 100 x 30k plates = 13M.
        eiv = 0.02 * 13_000_000
        bonus = 1 - (1 - 0.05) * (1 - 0.19)
        self.assertEqual(
            source.invention_fee.gross, int(eiv * 0.10 * (1 - bonus) * 0.5)
        )
        self.assertEqual(source.invention_fee.scc, int(eiv * 0.04))
        self.assertEqual(source.invention_fee.facility_tax, int(eiv * 0.0075))
        # Copy fee: 2% of the T1 hull's EIV (1M Tritanium at 5 ISK).
        self.assertEqual(source.copy_fee.scc, int(0.02 * 5_000_000 * 0.04))
        # Invention time: Sotiyo -30%, lab rig -38%, Advanced Industry V -15%.
        self.assertAlmostEqual(
            source.invention_seconds, 128_100 * 0.7 * 0.62 * 0.85
        )

    def test_plan_uses_the_copy_on_the_root_and_bpos_below(self):
        plan = plan_invented_build(HAC, 2, facility="amamake")
        best = plan.invention.best
        jobs = {job.product_type_id: job for job in plan.jobs}
        self.assertAlmostEqual(jobs[HAC].blueprint_me, best.copy_me / 100.0)
        self.assertAlmostEqual(jobs[HAC].blueprint_te, best.copy_te / 100.0)
        self.assertEqual(jobs[HAC].job_class, JobClass.SHIP_MANUFACTURING)
        # The root is split per copy; components keep the researched BPO.
        self.assertEqual(jobs[HAC].runs_per_job, min(best.runs_per_copy, 2))
        self.assertAlmostEqual(jobs[PLATE].blueprint_me, 0.10)
        self.assertAlmostEqual(jobs[CRUISER].blueprint_me, 0.10)
        self.assertEqual(plan.root_blueprint.runs_per_copy, best.runs_per_copy)

    def test_plan_build_without_root_blueprint_is_unchanged(self):
        before = plan_build(HAC, quantity=3, facility="amamake")
        self.assertIsNone(before.root_blueprint)
        self.assertTrue(all(job.blueprint_me == 0.10 for job in before.jobs))

    def test_cost_adds_invention_outside_manufacturing(self):
        plan = plan_invented_build(HAC, 1, facility="amamake")
        cost = cost_build_plan(plan)
        best = plan.invention.best
        self.assertEqual(
            cost.invention_isk,
            round(best.invention_materials_isk)
            + round(best.invention_job_costs_isk),
        )
        self.assertGreater(cost.invention_isk, 0)
        self.assertEqual(
            cost.grand_total_isk, cost.manufacturing_isk + cost.invention_isk
        )
        keys = {item.key for item in cost.line_items}
        self.assertTrue({"invention_materials", "invention_jobs"} <= keys)
        without = cost_build_plan(plan, include_invention=False)
        self.assertEqual(without.invention_isk, 0)
        self.assertEqual(without.manufacturing_isk, cost.manufacturing_isk)

    def test_plan_item_cost_kind_and_supplied_copy(self):
        invented = plan_item_cost(HAC, PlanCostOptions.planner_defaults())
        self.assertEqual(invented.kind, "T2")
        self.assertGreater(invented.invention_isk, 0)
        supplied = plan_item_cost(
            HAC,
            PlanCostOptions.planner_defaults(include_invention=False),
        )
        self.assertEqual(supplied.invention_isk, 0)
        self.assertEqual(supplied.kind, "T2")
        t1 = plan_item_cost(CRUISER, PlanCostOptions.planner_defaults())
        self.assertEqual(t1.kind, "T1")
        self.assertEqual(t1.invention_isk, 0)

    def test_explicit_decryptor_and_none(self):
        none = quote_invention(
            HAC, 1, request=InventionRequest(decryptor="none")
        )
        self.assertIsNone(none.best.decryptor.type_id)
        self.assertEqual(none.alternatives, [])
        acc = quote_invention(
            HAC, 1, request=InventionRequest(decryptor="34201")
        )
        self.assertEqual(acc.best.decryptor.type_id, 34201)
        self.assertEqual((acc.best.copy_me, acc.best.runs_per_copy), (4, 2))
        with self.assertRaises(ValueError):
            quote_invention(HAC, 1, request=InventionRequest(decryptor="123"))

    def test_invention_dict_has_buy_list_and_alternatives(self):
        data = invention_to_dict(quote_invention(HAC, 1))
        self.assertEqual(data["kind"], "T2")
        names = {row["name"] for row in data["inputs"]}
        self.assertTrue({"Datacore - Toy A", "Datacore - Toy B"} <= names)
        self.assertEqual(len(data["alternatives"]), 2)
        self.assertGreaterEqual(data["attempts_p90"], data["buy_attempts"])

    def test_equipment_root_gets_no_ship_rig(self):
        plan = plan_build(MODULE, quantity=1, facility="amamake")
        (job,) = plan.jobs
        self.assertEqual(job.job_class, JobClass.EQUIPMENT_MANUFACTURING)
        # Sotiyo role ME 1% only; the XL ship rig used to add 3.8%.
        self.assertAlmostEqual(job.me_total, 1 - (1 - 0.10) * (1 - 0.01))

    def test_root_blueprint_override(self):
        plan = plan_build(
            HAC,
            quantity=3,
            facility="amamake",
            root_blueprint=RootBlueprint(me=0.04, te=0.04, runs_per_copy=1),
        )
        jobs = {job.product_type_id: job for job in plan.jobs}
        self.assertEqual(jobs[HAC].job_count, 3)
        self.assertEqual(jobs[PLATE].job_count, 1)
        self.assertAlmostEqual(jobs[HAC].blueprint_me, 0.04)


class InventedPlanEndpointTests(ToyHacFixture):
    def _post(self, **body):
        return Client().post(
            "/api/industry/planner/plans",
            data={"product_type_id": HAC, "quantity": 1, **body},
            content_type="application/json",
        )

    def test_invent_by_default(self):
        response = self._post()
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["blueprint_source"], "invent")
        self.assertEqual(data["default_blueprint_me"], 10.0)
        self.assertIsNotNone(data["invention"])
        self.assertEqual(
            data["root_blueprint_me"], data["invention"]["copy_me"]
        )
        self.assertGreater(data["cost_breakdown"]["invention_isk"], 0)

    def test_supplied_copy_skips_invention(self):
        response = self._post(
            blueprint_source="supplied_bpc", bpc_me=4, bpc_te=10
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["blueprint_source"], "supplied_bpc")
        self.assertIsNone(data["invention"])
        self.assertAlmostEqual(data["root_blueprint_me"], 4.0)
        self.assertEqual(data["cost_breakdown"]["invention_isk"], 0)

    def test_bad_options_are_400(self):
        self.assertEqual(self._post(decryptor="999").status_code, 400)
        self.assertEqual(self._post(blueprint_source="bpo").status_code, 400)
        self.assertEqual(
            self._post(invention_skills={"science_1": 7}).status_code, 400
        )

    def test_t1_product_is_unchanged(self):
        response = self._post(product_type_id=CRUISER)
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["blueprint_source"], "bpo")
        self.assertIsNone(data["invention"])
        self.assertIsNone(data["root_blueprint_me"])


class ProductBuildInventionTests(ToyHacFixture):
    def test_build_tab_shows_how_the_copy_is_invented(self):
        product = IndustryProduct.objects.create(
            eve_type_id=HAC, strategy="produced"
        )
        response = Client().get(f"/api/industry/products/{product.pk}/build")
        self.assertEqual(response.status_code, 200, response.content)
        invention = response.json()["invention"]
        self.assertEqual(invention["kind"], "T2")
        (source,) = invention["sources"]
        self.assertEqual(source["name"], "Toy Cruiser Blueprint")
        self.assertAlmostEqual(source["base_chance"], 0.26)
        self.assertEqual(len(source["datacores"]), 2)
        self.assertIsNotNone(invention["decryptor_name"])
        self.assertGreater(invention["cost_per_unit"], 0)

    def test_t1_build_tab_has_no_invention(self):
        product = IndustryProduct.objects.create(
            eve_type_id=CRUISER, strategy="produced"
        )
        data = (
            Client().get(f"/api/industry/products/{product.pk}/build").json()
        )
        self.assertIsNone(data["invention"])
        self.assertIsNone(data["invention_cost"])


class InventionEndpointTests(ToyHacFixture):
    def test_info_lists_sources_and_decryptors(self):
        data = Client().get(f"/api/industry/planner/invention/{HAC}").json()
        self.assertEqual(data["kind"], "T2")
        self.assertEqual(data["sources"][0]["type_id"], CRUISER_BP)
        self.assertEqual(
            {d["type_id"] for d in data["decryptors"]}, {34201, 34208}
        )
        missing = Client().get(f"/api/industry/planner/invention/{CRUISER}")
        self.assertEqual(missing.status_code, 404)

    def test_quote_matches_the_plan(self):
        quote_data = (
            Client()
            .get(f"/api/industry/planner/invention/{HAC}/quote?quantity=2")
            .json()
        )
        plan_data = (
            Client()
            .post(
                "/api/industry/planner/plans",
                data={"product_type_id": HAC, "quantity": 2},
                content_type="application/json",
            )
            .json()
        )
        self.assertEqual(quote_data, plan_data["invention"])
        none = (
            Client()
            .get(f"/api/industry/planner/invention/{HAC}/quote?decryptor=none")
            .json()
        )
        self.assertIsNone(none["decryptor_type_id"])
        bad = Client().get(
            f"/api/industry/planner/invention/{HAC}/quote?encryption=9"
        )
        self.assertEqual(bad.status_code, 400)
