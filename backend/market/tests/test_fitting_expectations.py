from app.test import TestCase
from eveuniverse.models import EveCategory, EveGroup, EveType

from eveonline.models import EveLocation
from fittings.models import EveFitting
from market.models import (
    EveMarketFittingExpectation,
    EveMarketItemExpectation,
    get_effective_item_expectations,
    parse_eft_items,
)


def _make_eve_type(type_id, name):
    cat, _ = EveCategory.objects.get_or_create(
        id=1, defaults={"name": "Module", "published": True}
    )
    grp, _ = EveGroup.objects.get_or_create(
        id=1,
        defaults={"name": "General", "published": True, "eve_category": cat},
    )
    return EveType.objects.create(
        id=type_id, name=name, published=True, eve_group=grp
    )


RIFTER_EFT = """\
[Rifter, AC Rifter]

Damage Control II
400mm Rolled Tungsten Compact Plates
Multispectrum Coating II
Counterbalanced Compact Gyrostabilizer

5MN Quad LiF Restrained Microwarpdrive
Initiated Compact Warp Scrambler
Fleeting Compact Stasis Webifier

150mm Light Prototype Automatic Cannon
150mm Light Prototype Automatic Cannon
150mm Light Prototype Automatic Cannon

Small Ancillary Current Router I
Small Trimark Armor Pump I
Small Trimark Armor Pump I

Nanite Repair Paste x5
Fusion S x2000
Republic Fleet EMP S x720
"""


class ParseEftItemsTestCase(TestCase):
    def test_parses_ship(self):
        items = parse_eft_items(RIFTER_EFT)
        self.assertEqual(items["Rifter"], 1)

    def test_parses_single_modules(self):
        items = parse_eft_items(RIFTER_EFT)
        self.assertEqual(items["Damage Control II"], 1)
        self.assertEqual(items["Multispectrum Coating II"], 1)

    def test_stacks_duplicate_modules(self):
        items = parse_eft_items(RIFTER_EFT)
        self.assertEqual(items["150mm Light Prototype Automatic Cannon"], 3)
        self.assertEqual(items["Small Trimark Armor Pump I"], 2)

    def test_parses_cargo_with_quantity(self):
        items = parse_eft_items(RIFTER_EFT)
        self.assertEqual(items["Nanite Repair Paste"], 5)
        self.assertEqual(items["Fusion S"], 2000)
        self.assertEqual(items["Republic Fleet EMP S"], 720)

    def test_skips_empty_slots(self):
        eft = "[Rifter, Empty Rifter]\n\n[Empty Low slot]\n[Empty Med slot]\nDamage Control II\n"
        items = parse_eft_items(eft)
        self.assertNotIn("[Empty Low slot]", items)
        self.assertNotIn("[Empty Med slot]", items)
        self.assertEqual(items["Damage Control II"], 1)

    def test_empty_string(self):
        self.assertEqual(parse_eft_items(""), {})

    def test_total_unique_items(self):
        items = parse_eft_items(RIFTER_EFT)
        expected_unique = {
            "Rifter",
            "Damage Control II",
            "400mm Rolled Tungsten Compact Plates",
            "Multispectrum Coating II",
            "Counterbalanced Compact Gyrostabilizer",
            "5MN Quad LiF Restrained Microwarpdrive",
            "Initiated Compact Warp Scrambler",
            "Fleeting Compact Stasis Webifier",
            "150mm Light Prototype Automatic Cannon",
            "Small Ancillary Current Router I",
            "Small Trimark Armor Pump I",
            "Nanite Repair Paste",
            "Fusion S",
            "Republic Fleet EMP S",
        }
        self.assertEqual(set(items.keys()), expected_unique)


class EveMarketFittingExpectationTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.location = EveLocation.objects.create(
            location_id=2001,
            location_name="Staging Keepstar",
            market_active=True,
            solar_system_id=30000001,
        )
        self.fitting = EveFitting.objects.create(
            name="AC Rifter",
            eft_format=RIFTER_EFT,
            ship_id=587,
        )

    def test_get_item_quantities_multiplies_by_expectation(self):
        exp = EveMarketFittingExpectation.objects.create(
            fitting=self.fitting,
            location=self.location,
            quantity=10,
        )
        items = exp.get_item_quantities()
        self.assertEqual(items["Rifter"], 10)
        self.assertEqual(items["Damage Control II"], 10)
        self.assertEqual(items["150mm Light Prototype Automatic Cannon"], 30)
        self.assertEqual(items["Fusion S"], 20000)

    def test_str(self):
        exp = EveMarketFittingExpectation.objects.create(
            fitting=self.fitting,
            location=self.location,
            quantity=5,
        )
        self.assertIn("AC Rifter", str(exp))
        self.assertIn("x5", str(exp))


class GetEffectiveItemExpectationsTestCase(TestCase):
    """
    The effective expectation for each item at a location is the
    maximum across all independent sources (individual expectations
    and each fitting expectation).
    """

    def setUp(self):
        super().setUp()
        self.location = EveLocation.objects.create(
            location_id=3001,
            location_name="Market Hub",
            market_active=True,
            solar_system_id=30000002,
        )

        self.dc2_type = _make_eve_type(2048, "Damage Control II")
        self.rifter_type = _make_eve_type(587, "Rifter")

        self.fitting_a = EveFitting.objects.create(
            name="Fit A",
            eft_format="[Rifter, Fit A]\n\nDamage Control II\n",
            ship_id=587,
        )
        self.fitting_b = EveFitting.objects.create(
            name="Fit B",
            eft_format="[Rifter, Fit B]\n\nDamage Control II\n",
            ship_id=587,
        )

    def test_individual_only(self):
        EveMarketItemExpectation.objects.create(
            item=self.dc2_type, location=self.location, quantity=10
        )
        result = get_effective_item_expectations(self.location)
        self.assertEqual(result["Damage Control II"], 10)

    def test_fitting_only(self):
        EveMarketFittingExpectation.objects.create(
            fitting=self.fitting_a, location=self.location, quantity=15
        )
        result = get_effective_item_expectations(self.location)
        self.assertEqual(result["Damage Control II"], 15)
        self.assertEqual(result["Rifter"], 15)

    def test_max_across_sources(self):
        """
        individual=10, fitting_a=10, fitting_b=15 → max is 15 for DC2.
        """
        EveMarketItemExpectation.objects.create(
            item=self.dc2_type, location=self.location, quantity=10
        )
        EveMarketFittingExpectation.objects.create(
            fitting=self.fitting_a, location=self.location, quantity=10
        )
        EveMarketFittingExpectation.objects.create(
            fitting=self.fitting_b, location=self.location, quantity=15
        )
        result = get_effective_item_expectations(self.location)
        self.assertEqual(result["Damage Control II"], 15)

    def test_individual_larger_than_fittings(self):
        EveMarketItemExpectation.objects.create(
            item=self.dc2_type, location=self.location, quantity=50
        )
        EveMarketFittingExpectation.objects.create(
            fitting=self.fitting_a, location=self.location, quantity=10
        )
        result = get_effective_item_expectations(self.location)
        self.assertEqual(result["Damage Control II"], 50)

    def test_fitting_with_multiple_of_same_module(self):
        """A fitting with 3× guns: 10 fittings → 30 guns expected."""
        fitting_c = EveFitting.objects.create(
            name="Fit C",
            eft_format=(
                "[Rifter, Fit C]\n\n"
                "Damage Control II\n\n"
                "150mm Light Prototype Automatic Cannon\n"
                "150mm Light Prototype Automatic Cannon\n"
                "150mm Light Prototype Automatic Cannon\n"
            ),
            ship_id=587,
        )
        EveMarketFittingExpectation.objects.create(
            fitting=fitting_c, location=self.location, quantity=10
        )
        result = get_effective_item_expectations(self.location)
        self.assertEqual(result["150mm Light Prototype Automatic Cannon"], 30)
        self.assertEqual(result["Damage Control II"], 10)

    def test_empty_location(self):
        result = get_effective_item_expectations(self.location)
        self.assertEqual(result, {})
