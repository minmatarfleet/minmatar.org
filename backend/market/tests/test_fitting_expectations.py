from app.test import TestCase
from eveuniverse.models import EveCategory, EveGroup, EveType

from eveonline.models import EveLocation
from fittings.eft import item_quantities
from fittings.models import EveFitting
from market.helpers.contract_match import (
    fitting_structural_type_quantities,
    fitting_type_quantities,
)
from market.models import (
    EveMarketContractExpectation,
    EveMarketFittingExpectation,
    EveMarketItemExpectation,
    _get_consumable_items,
    get_effective_item_expectations,
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


def rifter_eft(fit_name: str = "AC Rifter") -> str:
    """RIFTER_EFT with a unique EFT header name (required since name == EFT name)."""
    body = RIFTER_EFT.split("\n", 1)[1]
    return f"[Rifter, {fit_name}]\n{body}"


class ParseEftItemsTestCase(TestCase):
    """Market's EFT projection: fittings.eft.item_quantities."""

    def test_parses_ship(self):
        items = item_quantities(RIFTER_EFT)
        self.assertEqual(items["Rifter"], 1)

    def test_parses_single_modules(self):
        items = item_quantities(RIFTER_EFT)
        self.assertEqual(items["Damage Control II"], 1)
        self.assertEqual(items["Multispectrum Coating II"], 1)

    def test_stacks_duplicate_modules(self):
        items = item_quantities(RIFTER_EFT)
        self.assertEqual(items["150mm Light Prototype Automatic Cannon"], 3)
        self.assertEqual(items["Small Trimark Armor Pump I"], 2)

    def test_parses_cargo_with_quantity(self):
        items = item_quantities(RIFTER_EFT)
        self.assertEqual(items["Nanite Repair Paste"], 5)
        self.assertEqual(items["Fusion S"], 2000)
        self.assertEqual(items["Republic Fleet EMP S"], 720)

    def test_skips_empty_slots(self):
        eft = "[Rifter, Empty Rifter]\n\n[Empty Low slot]\n[Empty Med slot]\nDamage Control II\n"
        items = item_quantities(eft)
        self.assertNotIn("[Empty Low slot]", items)
        self.assertNotIn("[Empty Med slot]", items)
        self.assertEqual(items["Damage Control II"], 1)

    def test_empty_string(self):
        self.assertEqual(item_quantities(""), {})

    def test_total_unique_items(self):
        items = item_quantities(RIFTER_EFT)
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


# Same fit as copied from the EVE client: charges loaded in the guns and
# an offline module. The old market parser kept these lines whole, so the
# cannons, the scram and the loaded ammo never resolved to a type.
CHARGED_RIFTER_EFT = """\
[Rifter, Charged Rifter]

Damage Control II

Initiated Compact Warp Scrambler /offline

150mm Light Prototype Automatic Cannon, Republic Fleet EMP S
150mm Light Prototype Automatic Cannon, Republic Fleet EMP S
150mm Light Prototype Automatic Cannon, Republic Fleet EMP S

Republic Fleet EMP S x720
"""


class ChargedFitTestCase(TestCase):
    """Fits with loaded charges and offline modules (BM-1)."""

    def setUp(self):
        super().setUp()
        self.rifter = _make_typed_eve_type(587, "Rifter", 6, "Ship")
        self.dc = _make_typed_eve_type(2048, "Damage Control II", 7, "Module")
        self.scram = _make_typed_eve_type(
            5399, "Initiated Compact Warp Scrambler", 7, "Module"
        )
        self.cannon = _make_typed_eve_type(
            9071, "150mm Light Prototype Automatic Cannon", 7, "Module"
        )
        self.emp = _make_typed_eve_type(
            21894, "Republic Fleet EMP S", 8, "Charge"
        )
        self.fitting = EveFitting.objects.create(
            name="Charged Rifter",
            eft_format=CHARGED_RIFTER_EFT,
            ship_id=587,
        )

    def test_item_quantities_split_module_and_charge(self):
        self.assertEqual(
            item_quantities(CHARGED_RIFTER_EFT),
            {
                "Rifter": 1,
                "Damage Control II": 1,
                "Initiated Compact Warp Scrambler": 1,
                "150mm Light Prototype Automatic Cannon": 3,
                # 720 in cargo plus one loaded per gun.
                "Republic Fleet EMP S": 723,
            },
        )

    def test_shopping_list_has_the_guns_and_the_scram(self):
        self.assertEqual(
            fitting_type_quantities(self.fitting),
            {
                self.rifter.id: 1,
                self.dc.id: 1,
                self.scram.id: 1,
                self.cannon.id: 3,
                self.emp.id: 723,
            },
        )

    def test_contract_match_scores_the_guns(self):
        self.assertEqual(
            fitting_structural_type_quantities(self.fitting),
            {
                self.rifter.id: 1,
                self.dc.id: 1,
                self.scram.id: 1,
                self.cannon.id: 3,
            },
        )

    def test_presence_catalog_and_consumables(self):
        location = EveLocation.objects.create(
            location_id=2002,
            location_name="Charged Keepstar",
            market_active=True,
            solar_system_id=30000001,
        )
        exp = EveMarketFittingExpectation.objects.create(
            fitting=self.fitting, location=location
        )
        self.assertEqual(
            exp.get_item_names(),
            {
                "Rifter",
                "Damage Control II",
                "Initiated Compact Warp Scrambler",
                "150mm Light Prototype Automatic Cannon",
                "Republic Fleet EMP S",
            },
        )
        self.assertEqual(
            _get_consumable_items(self.fitting),
            {"Republic Fleet EMP S": 723},
        )


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

    def test_get_item_quantities_is_presence(self):
        exp = EveMarketFittingExpectation.objects.create(
            fitting=self.fitting,
            location=self.location,
            quantity=10,
        )
        items = exp.get_item_quantities()
        self.assertEqual(items["Rifter"], 1)
        self.assertEqual(items["Damage Control II"], 1)
        self.assertEqual(items["150mm Light Prototype Automatic Cannon"], 1)
        self.assertEqual(items["Fusion S"], 1)

    def test_str(self):
        exp = EveMarketFittingExpectation.objects.create(
            fitting=self.fitting,
            location=self.location,
            quantity=5,
        )
        self.assertIn("AC Rifter", str(exp))
        self.assertIn("Staging Keepstar", str(exp))
        self.assertNotIn("x5", str(exp))


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
        self.assertEqual(result["Damage Control II"], 1)

    def test_fitting_only(self):
        EveMarketFittingExpectation.objects.create(
            fitting=self.fitting_a, location=self.location, quantity=15
        )
        result = get_effective_item_expectations(self.location)
        self.assertEqual(result["Damage Control II"], 1)
        self.assertEqual(result["Rifter"], 1)

    def test_pinned_overrides_fitting_max(self):
        """
        Pinned item expectation still wins for that item (presence target 1).
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
        self.assertEqual(result["Damage Control II"], 1)

    def test_individual_larger_than_fittings(self):
        EveMarketItemExpectation.objects.create(
            item=self.dc2_type, location=self.location, quantity=50
        )
        EveMarketFittingExpectation.objects.create(
            fitting=self.fitting_a, location=self.location, quantity=10
        )
        result = get_effective_item_expectations(self.location)
        self.assertEqual(result["Damage Control II"], 1)

    def test_fitting_with_multiple_of_same_module(self):
        """A fitting with 3× guns still contributes presence 1 per item name."""
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
        self.assertEqual(result["150mm Light Prototype Automatic Cannon"], 1)
        self.assertEqual(result["Damage Control II"], 1)

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
        self.assertEqual(result["Fusion S"], 1)
        self.assertEqual(result["Republic Fleet EMP S"], 1)

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
        """Pinned and contract consumables both resolve to presence 1."""
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
        self.assertEqual(result["Fusion S"], 1)

    def test_contract_consumable_larger_than_item_expectation(self):
        """Pinned item expectation overrides contract consumable contribution."""
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
        self.assertEqual(result["Fusion S"], 1)

    def test_multiple_contract_expectations_max(self):
        """Two contract expectations still contribute presence 1 per item."""
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
        self.assertEqual(result["Fusion S"], 1)
