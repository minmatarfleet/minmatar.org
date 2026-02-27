from app.test import TestCase
from eveuniverse.models import EveCategory, EveGroup, EveType

from eveonline.models import EveLocation
from fittings.models import EveFitting
from market.models import (
    EveMarketContractExpectation,
    EveMarketFittingExpectation,
    EveMarketItemExpectation,
    _get_consumable_items,
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


def _make_typed_eve_type(
    type_id, name, category_id, category_name, group_id=None
):
    """Create an EveType with a specific category (Ship, Module, Charge, etc.)."""
    cat, _ = EveCategory.objects.get_or_create(
        id=category_id, defaults={"name": category_name, "published": True}
    )
    gid = group_id or category_id * 100
    grp, _ = EveGroup.objects.get_or_create(
        id=gid,
        defaults={
            "name": f"{category_name} Group",
            "published": True,
            "eve_category": cat,
        },
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


AMMO_RIFTER_EFT = """\
[Rifter, Ammo Rifter]

Damage Control II

150mm Light Prototype Automatic Cannon

Fusion S x2000
Republic Fleet EMP S x720
"""


class GetConsumableItemsTestCase(TestCase):
    """Tests for _get_consumable_items — extracting only charges/drones/etc."""

    def setUp(self):
        super().setUp()
        _make_typed_eve_type(587, "Rifter", 6, "Ship")
        _make_typed_eve_type(2048, "Damage Control II", 7, "Module")
        _make_typed_eve_type(
            9900, "150mm Light Prototype Automatic Cannon", 7, "Module"
        )
        _make_typed_eve_type(9001, "Fusion S", 8, "Charge")
        _make_typed_eve_type(9002, "Republic Fleet EMP S", 8, "Charge")

        self.fitting = EveFitting.objects.create(
            name="Ammo Rifter",
            eft_format=AMMO_RIFTER_EFT,
            ship_id=587,
        )

    def test_excludes_ship_and_modules(self):
        result = _get_consumable_items(self.fitting)
        self.assertNotIn("Rifter", result)
        self.assertNotIn("Damage Control II", result)
        self.assertNotIn("150mm Light Prototype Automatic Cannon", result)

    def test_includes_charges(self):
        result = _get_consumable_items(self.fitting)
        self.assertEqual(result["Fusion S"], 2000)
        self.assertEqual(result["Republic Fleet EMP S"], 720)

    def test_excludes_unknown_items(self):
        fitting = EveFitting.objects.create(
            name="Unknown Fit",
            eft_format="[Rifter, Unknown Fit]\n\nMystery Module\nFusion S x100\n",
            ship_id=587,
        )
        result = _get_consumable_items(fitting)
        self.assertNotIn("Mystery Module", result)
        self.assertEqual(result["Fusion S"], 100)

    def test_includes_drones(self):
        _make_typed_eve_type(2456, "Hobgoblin II", 18, "Drone")
        fitting = EveFitting.objects.create(
            name="Drone Fit",
            eft_format="[Rifter, Drone Fit]\n\nDamage Control II\n\nHobgoblin II x5\n",
            ship_id=587,
        )
        result = _get_consumable_items(fitting)
        self.assertEqual(result["Hobgoblin II"], 5)
        self.assertNotIn("Damage Control II", result)


class ContractExpectationConsumablesTestCase(TestCase):
    """
    Contract fitting expectations should contribute their consumable
    items (charges, drones, etc.) to effective sell-order expectations.
    """

    def setUp(self):
        super().setUp()
        self.location = EveLocation.objects.create(
            location_id=4001,
            location_name="Contract Hub",
            market_active=True,
            solar_system_id=30000003,
        )
        _make_typed_eve_type(587, "Rifter", 6, "Ship")
        _make_typed_eve_type(2048, "Damage Control II", 7, "Module")
        _make_typed_eve_type(
            9900, "150mm Light Prototype Automatic Cannon", 7, "Module"
        )
        _make_typed_eve_type(9001, "Fusion S", 8, "Charge")
        _make_typed_eve_type(9002, "Republic Fleet EMP S", 8, "Charge")

        self.fitting = EveFitting.objects.create(
            name="Ammo Rifter",
            eft_format=AMMO_RIFTER_EFT,
            ship_id=587,
        )

    def test_contract_consumables_appear_in_effective(self):
        EveMarketContractExpectation.objects.create(
            fitting=self.fitting,
            location=self.location,
            quantity=5,
        )
        result = get_effective_item_expectations(self.location)
        self.assertEqual(result["Fusion S"], 10000)
        self.assertEqual(result["Republic Fleet EMP S"], 3600)

    def test_contract_does_not_add_ship_or_modules(self):
        EveMarketContractExpectation.objects.create(
            fitting=self.fitting,
            location=self.location,
            quantity=5,
        )
        result = get_effective_item_expectations(self.location)
        self.assertNotIn("Rifter", result)
        self.assertNotIn("Damage Control II", result)
        self.assertNotIn("150mm Light Prototype Automatic Cannon", result)

    def test_max_across_contract_and_item_expectations(self):
        """Contract gives 10 000 Fusion S; item expectation gives 15 000 → max wins."""
        fusion_type = EveType.objects.get(name="Fusion S")
        EveMarketItemExpectation.objects.create(
            item=fusion_type, location=self.location, quantity=15000
        )
        EveMarketContractExpectation.objects.create(
            fitting=self.fitting,
            location=self.location,
            quantity=5,
        )
        result = get_effective_item_expectations(self.location)
        self.assertEqual(result["Fusion S"], 15000)

    def test_contract_consumable_larger_than_item_expectation(self):
        """Contract gives 10 000 Fusion S; item expectation gives 5 000 → contract wins."""
        fusion_type = EveType.objects.get(name="Fusion S")
        EveMarketItemExpectation.objects.create(
            item=fusion_type, location=self.location, quantity=5000
        )
        EveMarketContractExpectation.objects.create(
            fitting=self.fitting,
            location=self.location,
            quantity=5,
        )
        result = get_effective_item_expectations(self.location)
        self.assertEqual(result["Fusion S"], 10000)

    def test_multiple_contract_expectations_max(self):
        """Two contract expectations for different fittings; max per item wins."""
        fitting_b = EveFitting.objects.create(
            name="Big Ammo Rifter",
            eft_format="[Rifter, Big Ammo Rifter]\n\nDamage Control II\n\nFusion S x5000\n",
            ship_id=587,
        )
        EveMarketContractExpectation.objects.create(
            fitting=self.fitting,
            location=self.location,
            quantity=5,
        )
        EveMarketContractExpectation.objects.create(
            fitting=fitting_b,
            location=self.location,
            quantity=3,
        )
        result = get_effective_item_expectations(self.location)
        # fitting: 2000*5=10000, fitting_b: 5000*3=15000
        self.assertEqual(result["Fusion S"], 15000)
