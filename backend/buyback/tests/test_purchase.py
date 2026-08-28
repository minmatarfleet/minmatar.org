"""Tests for buyback remaining stock, fill matching, and purchase orders."""

from decimal import Decimal
from unittest.mock import patch

from django.test import Client
from django.utils import timezone

from app.test import TestCase
from buyback.helpers.purchase_fill import fill_purchase
from buyback.helpers.purchase_orders import (
    try_complete_from_outbound_contracts,
)
from buyback.helpers.remaining import remaining_sale_quantities
from buyback.helpers.sell_pricing import unit_prices_for_types
from buyback.models import (
    BuybackHangarSnapshot,
    BuybackLedgerEntry,
    BuybackPurchaseOrder,
    EveBuybackSettings,
    SellPriceBasis,
)
from buyback.tests.helpers import BASE_URL, ensure_type
from eveonline.models import EveCharacter, EveCharacterSkill, EveLocation
from industry.helpers.facility_profiles import get_facility_refine_rate
from industry.helpers.reprocessing_skills import (
    SKILL_COHERENT_ORE_PROCESSING,
    SKILL_REPROCESSING,
    SKILL_REPROCESSING_EFFICIENCY,
    SKILL_SIMPLE_ORE_PROCESSING,
    SKILL_UBIQUITOUS_MOON_ORE_PROCESSING,
)
from market.models import EveMarketItemLocationPrice


def _ledger(*, eve_type, quantity, reason, source_id, **extra):
    defaults = {
        "reason": reason,
        "eve_type": eve_type,
        "quantity": quantity,
        "occurred_at": timezone.now(),
        "source_id": source_id,
    }
    defaults.update(extra)
    return BuybackLedgerEntry.objects.create(**defaults)


class RemainingSaleQuantitiesTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.ore = ensure_type(
            type_id=62518,
            name="Compressed Veldspar",
            group_id=462,
            group_name="Veldspar",
            category_id=25,
            category_name="Asteroid",
        )

    def test_inbound_minus_outbound_minus_pending(self):
        _ledger(
            eve_type=self.ore,
            quantity=100,
            reason=BuybackLedgerEntry.Reason.IN_CONTRACT,
            source_id="in:1",
        )
        _ledger(
            eve_type=self.ore,
            quantity=30,
            reason=BuybackLedgerEntry.Reason.SOLD_CONTRACT,
            source_id="out:1",
        )
        _ledger(
            eve_type=self.ore,
            quantity=99,
            reason=BuybackLedgerEntry.Reason.SOLD_ORDER,
            source_id="mkt:1",
        )
        self.assertEqual(remaining_sale_quantities(), {self.ore.id: 70})

    def test_pending_purchase_reduces_remaining(self):
        _ledger(
            eve_type=self.ore,
            quantity=50,
            reason=BuybackLedgerEntry.Reason.IN_CONTRACT,
            source_id="in:1",
        )
        order = BuybackPurchaseOrder.objects.create(
            created_by=self.user,
            paste="Compressed Veldspar\t10",
            contract_total=1,
            sell_price_basis=SellPriceBasis.JITA_SPLIT,
            sell_markup=0,
        )
        order.lines.create(
            eve_type=self.ore,
            name=self.ore.name,
            quantity=10,
            unit_price=Decimal("1.00"),
            line_total=Decimal("10.00"),
        )
        self.assertEqual(remaining_sale_quantities(), {self.ore.id: 40})

    def test_hangar_snapshot_caps_remaining_after_pending(self):
        _ledger(
            eve_type=self.ore,
            quantity=200,
            reason=BuybackLedgerEntry.Reason.IN_CONTRACT,
            source_id="in:1",
        )
        BuybackHangarSnapshot.objects.create(
            taken_at=timezone.now(),
            quantities={str(self.ore.id): 80},
        )
        order = BuybackPurchaseOrder.objects.create(
            created_by=self.user,
            paste="Compressed Veldspar\t10",
            contract_total=1,
            sell_price_basis=SellPriceBasis.JITA_SPLIT,
            sell_markup=0,
        )
        order.lines.create(
            eve_type=self.ore,
            name=self.ore.name,
            quantity=10,
            unit_price=Decimal("1.00"),
            line_total=Decimal("10.00"),
        )
        self.assertEqual(remaining_sale_quantities(), {self.ore.id: 70})


class SellPricingTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.ore = ensure_type(
            type_id=62518,
            name="Compressed Veldspar",
            group_id=462,
            group_name="Veldspar",
            category_id=25,
            category_name="Asteroid",
        )
        self.jita = EveLocation.objects.create(
            location_id=60003760,
            location_name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            solar_system_id=30000142,
            solar_system_name="Jita",
            short_name="Jita",
            region_id=10000002,
            price_baseline=True,
            prices_active=True,
            market_active=False,
        )
        EveMarketItemLocationPrice.objects.create(
            location=self.jita,
            item=self.ore,
            buy_price=Decimal("10.00"),
            sell_price=Decimal("14.00"),
            split_price=Decimal("12.00"),
        )

    def test_jita_split_with_zero_markup(self):
        settings = EveBuybackSettings.load()
        settings.sell_price_basis = SellPriceBasis.JITA_SPLIT
        settings.sell_markup = 0
        settings.save()
        prices = unit_prices_for_types([self.ore.id], settings=settings)
        self.assertEqual(prices[self.ore.id], Decimal("12.00"))

    def test_markup_applies_to_split(self):
        settings = EveBuybackSettings.load()
        settings.sell_price_basis = SellPriceBasis.JITA_SPLIT
        settings.sell_markup = 0.05
        settings.save()
        prices = unit_prices_for_types([self.ore.id], settings=settings)
        self.assertEqual(prices[self.ore.id], Decimal("12.60"))


@patch("industry.helpers.compressed_ore._ensure_type_materials_loaded")
class PurchaseFillTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.ore = ensure_type(
            type_id=62518,
            name="Compressed Veldspar",
            group_id=462,
            group_name="Veldspar",
            category_id=25,
            category_name="Asteroid",
        )
        self.grade = ensure_type(
            type_id=62522,
            name="Compressed Veldspar II-Grade",
            group_id=462,
            group_name="Veldspar",
            category_id=25,
            category_name="Asteroid",
        )
        self.water = ensure_type(
            type_id=3645,
            name="Water",
            group_id=1042,
            group_name="Basic Commodities - Tier 1",
            category_id=43,
            category_name="Planetary Commodities",
        )
        self.trit = ensure_type(
            type_id=34,
            name="Tritanium",
            group_id=18,
            group_name="Mineral",
            category_id=4,
            category_name="Material",
        )
        jita = EveLocation.objects.create(
            location_id=60003760,
            location_name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            solar_system_id=30000142,
            solar_system_name="Jita",
            short_name="Jita",
            region_id=10000002,
            price_baseline=True,
            prices_active=True,
            market_active=False,
        )
        for eve_type, split in (
            (self.ore, "12.00"),
            (self.grade, "13.00"),
            (self.water, "100.00"),
        ):
            EveMarketItemLocationPrice.objects.create(
                location=jita,
                item=eve_type,
                buy_price=Decimal(split),
                sell_price=Decimal(split),
                split_price=Decimal(split),
            )

    def test_pi_exact_match(self, unused_mock_esi):
        _ledger(
            eve_type=self.water,
            quantity=50,
            reason=BuybackLedgerEntry.Reason.IN_CONTRACT,
            source_id="in:water",
        )
        fill = fill_purchase("Water\t20")
        self.assertEqual(len(fill.picks), 1)
        self.assertEqual(fill.picks[0].name, "Water")
        self.assertEqual(fill.picks[0].quantity, 20)
        self.assertEqual(fill.picks[0].fill_source, "exact")
        self.assertEqual(fill.contract_total, 2000)
        self.assertEqual(fill.janice_tsv, "Water\t20")
        self.assertEqual(fill.shortfalls, [])

    def test_tritanium_fills_compressed_veldspar(self, unused_mock_esi):
        _ledger(
            eve_type=self.ore,
            quantity=1000,
            reason=BuybackLedgerEntry.Reason.IN_CONTRACT,
            source_id="in:ore",
        )
        fill = fill_purchase("Tritanium\t1000")
        self.assertEqual(len(fill.picks), 1)
        self.assertEqual(fill.picks[0].name, "Compressed Veldspar")
        self.assertEqual(fill.picks[0].fill_source, "refine")
        self.assertGreater(fill.picks[0].quantity, 0)
        self.assertTrue(fill.janice_tsv.startswith("Compressed Veldspar\t"))
        self.assertNotEqual(fill.picks[0].name, "Veldspar")

    def test_compressed_veldspar_filled_by_grade_variant(
        self, unused_mock_esi
    ):
        _ledger(
            eve_type=self.grade,
            quantity=500,
            reason=BuybackLedgerEntry.Reason.IN_CONTRACT,
            source_id="in:grade",
        )
        fill = fill_purchase("Compressed Veldspar\t100")
        self.assertEqual(len(fill.picks), 1)
        self.assertEqual(fill.picks[0].name, "Compressed Veldspar II-Grade")
        self.assertIn("Compressed Veldspar II-Grade\t", fill.janice_tsv)
        self.assertNotIn("Veldspar\t100", fill.janice_tsv)

    def test_amamake_uses_facility_refine_not_settings(self, unused_mock_esi):
        _ledger(
            eve_type=self.ore,
            quantity=10000,
            reason=BuybackLedgerEntry.Reason.IN_CONTRACT,
            source_id="in:ore-facility",
        )
        settings = EveBuybackSettings.load()
        settings.ore_refine = 0.85
        settings.save()
        settings_fill = fill_purchase("Tritanium\t1000")
        facility_fill = fill_purchase(
            "Tritanium\t1000",
            facility_key="amamake",
        )
        expected = get_facility_refine_rate("amamake")
        self.assertAlmostEqual(facility_fill.refine_rate, expected, places=7)
        self.assertEqual(facility_fill.facility_key, "amamake")
        self.assertEqual(facility_fill.facility_name, "Amamake")
        self.assertEqual(facility_fill.refine_rate_source, "facility_default")
        self.assertGreater(
            facility_fill.picks[0].quantity,
            settings_fill.picks[0].quantity,
        )

    def test_low_simple_ore_skill_needs_more_veldspar(self, unused_mock_esi):
        _ledger(
            eve_type=self.ore,
            quantity=100000,
            reason=BuybackLedgerEntry.Reason.IN_CONTRACT,
            source_id="in:ore-skills",
        )
        character = EveCharacter.objects.create(
            character_id=2122000001,
            character_name="Refine Pilot",
        )
        for skill_id, level, name in (
            (SKILL_REPROCESSING, 5, "Reprocessing"),
            (SKILL_REPROCESSING_EFFICIENCY, 5, "Reprocessing Efficiency"),
            (SKILL_SIMPLE_ORE_PROCESSING, 1, "Simple Ore Processing"),
            (SKILL_COHERENT_ORE_PROCESSING, 5, "Coherent Ore Processing"),
            (
                SKILL_UBIQUITOUS_MOON_ORE_PROCESSING,
                5,
                "Ubiquitous Moon Ore Processing",
            ),
        ):
            EveCharacterSkill.objects.create(
                character=character,
                skill_id=skill_id,
                skill_name=name,
                skill_points=level * 1000,
                skill_level=level,
            )
        maxed = fill_purchase("Tritanium\t10000", facility_key="amamake")
        skilled = fill_purchase(
            "Tritanium\t10000",
            facility_key="amamake",
            character=character,
        )
        self.assertEqual(skilled.refine_rate_source, "character")
        self.assertGreater(skilled.picks[0].quantity, maxed.picks[0].quantity)


class PurchaseOrderEndpointTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.setup_character()
        self.client = Client()
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}
        self.water = ensure_type(
            type_id=3645,
            name="Water",
            group_id=1042,
            group_name="Basic Commodities - Tier 1",
            category_id=43,
            category_name="Planetary Commodities",
        )
        jita = EveLocation.objects.create(
            location_id=60003760,
            location_name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            solar_system_id=30000142,
            solar_system_name="Jita",
            short_name="Jita",
            region_id=10000002,
            price_baseline=True,
            prices_active=True,
            market_active=False,
        )
        EveMarketItemLocationPrice.objects.create(
            location=jita,
            item=self.water,
            buy_price=Decimal("100.00"),
            sell_price=Decimal("100.00"),
            split_price=Decimal("100.00"),
        )
        _ledger(
            eve_type=self.water,
            quantity=50,
            reason=BuybackLedgerEntry.Reason.IN_CONTRACT,
            source_id="in:water",
        )

    def test_guest_can_fill(self):
        response = self.client.post(
            f"{BASE_URL}/stock/fill",
            data={"paste": "Water\t10"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["picks"][0]["quantity"], 10)
        self.assertEqual(data["contract_total"], 1000)

    def test_guest_cannot_fill_with_character(self):
        response = self.client.post(
            f"{BASE_URL}/stock/fill",
            data={"paste": "Water\t10", "character_id": 123456},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_logged_in_can_fill_with_character(self):
        response = self.client.post(
            f"{BASE_URL}/stock/fill",
            data={
                "paste": "Water\t10",
                "character_id": 123456,
                "facility_key": "amamake",
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["facility_key"], "amamake")
        self.assertGreater(response.json()["refine_rate"], 0)

    def test_cannot_fill_with_character_not_on_account(self):
        other = EveCharacter.objects.create(
            character_id=999999,
            character_name="Other Pilot",
        )
        response = self.client.post(
            f"{BASE_URL}/stock/fill",
            data={
                "paste": "Water\t10",
                "character_id": other.character_id,
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 403)

    def test_place_order_uses_refine_character(self):
        response = self.client.post(
            f"{BASE_URL}/stock/orders",
            data={
                "paste": "Water\t10",
                "source": "stockpile",
                "character_id": 123456,
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["character_id"], 123456)
        self.assertEqual(response.json()["character_name"], "Test Char")

    def test_unknown_facility_is_bad_request(self):
        response = self.client.post(
            f"{BASE_URL}/stock/fill",
            data={"paste": "Water\t10", "facility_key": "jita"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_guest_cannot_place(self):
        response = self.client.post(
            f"{BASE_URL}/stock/orders",
            data={"paste": "Water\t10"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_logged_in_user_can_place_and_pending_holds_stock(self):
        response = self.client.post(
            f"{BASE_URL}/stock/orders",
            data={"paste": "Water\t10", "source": "stockpile"},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["contract_total"], 1000)
        self.assertEqual(data["character_name"], "Test Char")
        self.assertIsNone(data["discord_thread_id"])
        self.assertEqual(remaining_sale_quantities()[self.water.id], 40)

        second = self.client.post(
            f"{BASE_URL}/stock/fill",
            data={"paste": "Water\t50"},
            content_type="application/json",
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["picks"][0]["quantity"], 40)
        self.assertEqual(second.json()["shortfalls"][0]["quantity"], 10)

    def test_second_place_cannot_take_already_reserved_stock(self):
        first = self.client.post(
            f"{BASE_URL}/stock/orders",
            data={"paste": "Water\t50", "source": "stockpile"},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(first.status_code, 201)
        second = self.client.post(
            f"{BASE_URL}/stock/orders",
            data={"paste": "Water\t50", "source": "stockpile"},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(second.status_code, 400)
        self.assertEqual(BuybackPurchaseOrder.objects.count(), 1)

    def test_buyer_cannot_complete(self):
        placed = self.client.post(
            f"{BASE_URL}/stock/orders",
            data={"paste": "Water\t10"},
            content_type="application/json",
            **self.auth,
        )
        order_id = placed.json()["id"]
        response = self.client.post(
            f"{BASE_URL}/stock/orders/{order_id}/complete",
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 403)

    def test_staff_can_complete_and_cancel_releases_stock(self):
        placed = self.client.post(
            f"{BASE_URL}/stock/orders",
            data={"paste": "Water\t10"},
            content_type="application/json",
            **self.auth,
        )
        order_id = placed.json()["id"]
        order = BuybackPurchaseOrder.objects.get(pk=order_id)
        _ledger(
            eve_type=self.water,
            quantity=10,
            reason=BuybackLedgerEntry.Reason.SOLD_CONTRACT,
            source_id="out:complete-test",
            counterparty_id=order.character_id,
        )
        self.user.is_staff = True
        self.user.save()

        complete = self.client.post(
            f"{BASE_URL}/stock/orders/{order_id}/complete",
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(complete.status_code, 200)
        self.assertEqual(complete.json()["status"], "completed")

        second = self.client.post(
            f"{BASE_URL}/stock/orders",
            data={"paste": "Water\t10"},
            content_type="application/json",
            **self.auth,
        )
        other_id = second.json()["id"]
        cancel = self.client.post(
            f"{BASE_URL}/stock/orders/{other_id}/cancel",
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(cancel.status_code, 200)
        self.assertEqual(cancel.json()["status"], "cancelled")
        self.assertEqual(remaining_sale_quantities()[self.water.id], 40)

    def test_operator_lists_pending(self):
        self.client.post(
            f"{BASE_URL}/stock/orders",
            data={"paste": "Water\t10"},
            content_type="application/json",
            **self.auth,
        )
        self.user.is_staff = True
        self.user.save()
        listed = self.client.get(f"{BASE_URL}/stock/orders", **self.auth)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["count"], 1)

    def test_auto_complete_from_outbound_contract(self):
        placed = self.client.post(
            f"{BASE_URL}/stock/orders",
            data={"paste": "Water\t10"},
            content_type="application/json",
            **self.auth,
        )
        order = BuybackPurchaseOrder.objects.get(pk=placed.json()["id"])
        _ledger(
            eve_type=self.water,
            quantity=10,
            reason=BuybackLedgerEntry.Reason.SOLD_CONTRACT,
            source_id="out:water",
            counterparty_id=order.character_id,
        )
        completed = try_complete_from_outbound_contracts()
        self.assertEqual(completed, 1)
        order.refresh_from_db()
        self.assertEqual(order.status, BuybackPurchaseOrder.Status.COMPLETED)

    def test_auto_complete_fifo_allocates_one_contract_across_orders(self):
        first = self.client.post(
            f"{BASE_URL}/stock/orders",
            data={"paste": "Water\t10"},
            content_type="application/json",
            **self.auth,
        )
        second = self.client.post(
            f"{BASE_URL}/stock/orders",
            data={"paste": "Water\t10"},
            content_type="application/json",
            **self.auth,
        )
        order_a = BuybackPurchaseOrder.objects.get(pk=first.json()["id"])
        order_b = BuybackPurchaseOrder.objects.get(pk=second.json()["id"])
        _ledger(
            eve_type=self.water,
            quantity=10,
            reason=BuybackLedgerEntry.Reason.SOLD_CONTRACT,
            source_id="out:fifo",
            counterparty_id=order_a.character_id,
        )
        completed = try_complete_from_outbound_contracts()
        self.assertEqual(completed, 1)
        order_a.refresh_from_db()
        order_b.refresh_from_db()
        self.assertEqual(order_a.status, BuybackPurchaseOrder.Status.COMPLETED)
        self.assertEqual(order_b.status, BuybackPurchaseOrder.Status.PENDING)

    def test_complete_without_outbound_contract_is_rejected(self):
        placed = self.client.post(
            f"{BASE_URL}/stock/orders",
            data={"paste": "Water\t10"},
            content_type="application/json",
            **self.auth,
        )
        order_id = placed.json()["id"]
        self.user.is_staff = True
        self.user.save()
        response = self.client.post(
            f"{BASE_URL}/stock/orders/{order_id}/complete",
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 400)

    def test_capabilities_staff(self):
        response = self.client.get(
            f"{BASE_URL}/stock/purchase-capabilities",
            **self.auth,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["can_manage"])
        self.user.is_staff = True
        self.user.save()
        response = self.client.get(
            f"{BASE_URL}/stock/purchase-capabilities",
            **self.auth,
        )
        self.assertTrue(response.json()["can_manage"])
