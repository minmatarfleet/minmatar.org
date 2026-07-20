from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from app.test import TestCase
from eveonline.client import EsiResponse
from eveonline.models import EveLocation
from eveuniverse.models import EveType
from fittings.models import (
    DOCTRINE_TYPE_NON_STRATEGIC,
    EveDoctrine,
    EveDoctrineFitting,
    EveFitting,
    FittingTag,
)
from market.admin_location_views import (
    _allowed_fitting_ids,
    market_location_fitting_expectations_view,
)
from market.helpers.contract_admin import build_location_contracts_context
from market.helpers.contract_match import (
    MATCH_THRESHOLD,
    is_match_accepted,
    match_contract_to_fitting,
    normalize_contract_items,
    score_contract_against_fitting,
)
from market.helpers.contract_stock import outstanding_stock_q
from market.helpers.contracts import create_or_update_contract_from_db_contract
from market.helpers.contract_items import apply_content_match
from market.helpers.contract_items import fetch_and_match_contract_items
from market.helpers.expectations_admin import (
    build_contract_expectation_rows,
    build_fitting_expectation_rows,
    build_location_contract_expectations_context,
    build_location_fitting_expectations_context,
    filter_contract_expectation_rows,
    filter_fitting_expectation_rows,
    save_contract_expectation_quantities,
    save_fitting_expectation_quantities,
)
from market.helpers.orders import process_structure_sell_orders_page
from market.helpers.pricing import get_volume_90d_by_type_id
from market.helpers.qualification import (
    get_qualified_contract_fittings,
    get_qualified_non_doctrine_sell_fittings,
    get_qualified_sell_fittings,
)
from market.helpers.sell_orders import (
    REASONABLE_JITA_PRICE_FLOOR,
    REASONABLE_MARKUP_MAX_PCT,
    _calculate_markup_pct,
    _format_reference_display,
    _order_quantity_counts_as_reasonable,
    _stock_level,
    build_unified_sell_order_rows,
    filter_sell_order_rows,
    save_sell_order_desired_quantities,
)
from market.helpers.sell_orders_changelist import (
    LocationSellOrdersModelAdmin,
    SellOrderListItem,
    _format_listed_qty_display,
    _sort_sell_order_rows,
)
from market.models import (
    EveMarketContract,
    EveMarketContractExpectation,
    EveMarketFittingExpectation,
    EveMarketItemExpectation,
    EveMarketItemOrder,
    get_effective_item_expectations,
)
from market.models.history import EveMarketItemHistory
from market.tests.test_fitting_expectations import (
    _make_eve_type,
    _make_typed_eve_type,
    rifter_eft,
)


def _make_location(**kwargs):
    defaults = {
        "location_id": 9001,
        "location_name": "Test Hub",
        "solar_system_id": 1,
        "solar_system_name": "Amamake",
        "short_name": "TEST",
        "region_id": 10000030,
        "market_active": True,
    }
    defaults.update(kwargs)
    return EveLocation.objects.create(**defaults)


class QualificationTestCase(TestCase):
    def setUp(self):
        self.location = _make_location(
            market_categories=[FittingTag.NANOGANG, FittingTag.NULLSEC]
        )
        self.matching = EveFitting.objects.create(
            name="[FL33T] Nanogang Rifter",
            eft_format=rifter_eft("[FL33T] Nanogang Rifter"),
            ship_id=587,
        )
        self.matching.set_tag_slugs([FittingTag.NANOGANG], write_history=False)
        self.non_matching = EveFitting.objects.create(
            name="[FL33T] Highsec Venture",
            eft_format="[Venture, [FL33T] Highsec Venture]\nMiner I",
            ship_id=32880,
        )
        self.non_matching.set_tag_slugs(
            [FittingTag.HIGHSEC], write_history=False
        )

    def test_sell_fittings_any_tag_match(self):
        qualified = list(get_qualified_sell_fittings(self.location))
        self.assertEqual([self.matching], qualified)

    def test_qualified_non_doctrine_sell_fittings_exclude_doctrine(self):
        doctrine = EveDoctrine.objects.create(
            name="Test Doctrine",
            type=DOCTRINE_TYPE_NON_STRATEGIC,
            description="test",
        )
        EveDoctrineFitting.objects.create(
            doctrine=doctrine,
            fitting=self.matching,
            role="primary",
        )
        qualified = list(
            get_qualified_non_doctrine_sell_fittings(self.location)
        )
        self.assertEqual(qualified, [])
        self.assertNotIn(self.matching, qualified)

    def test_contract_fittings_from_doctrine_location(self):
        doctrine = EveDoctrine.objects.create(
            name="Test Doctrine",
            type=DOCTRINE_TYPE_NON_STRATEGIC,
            description="test",
        )
        doctrine.locations.add(self.location)
        EveDoctrineFitting.objects.create(
            doctrine=doctrine,
            fitting=self.matching,
            role="primary",
        )
        qualified = list(get_qualified_contract_fittings(self.location))
        self.assertEqual([self.matching], qualified)


class PinningExpectationsTestCase(TestCase):
    def setUp(self):
        self.location = _make_location()
        self.rifter_type = _make_eve_type(587, "Rifter")
        self.ammo_type = _make_eve_type(12773, "Fusion S")
        self.fitting = EveFitting.objects.create(
            name="[FL33T] Rifter",
            eft_format=rifter_eft("[FL33T] Rifter"),
            ship_id=587,
        )
        EveMarketFittingExpectation.objects.create(
            fitting=self.fitting,
            location=self.location,
            quantity=10,
        )

    def test_pinned_item_overrides_fitting_piggyback(self):
        EveMarketItemExpectation.objects.create(
            item=self.ammo_type,
            location=self.location,
            quantity=500,
        )
        effective = get_effective_item_expectations(self.location)
        self.assertEqual(effective["Fusion S"], 500)
        self.assertNotEqual(effective["Fusion S"], 20000)

    def test_pinned_item_excluded_from_fitting_sum(self):
        EveMarketItemExpectation.objects.create(
            item=self.rifter_type,
            location=self.location,
            quantity=3,
        )
        effective = get_effective_item_expectations(self.location)
        self.assertEqual(effective["Rifter"], 3)


class BuyOrderSyncTestCase(TestCase):
    def setUp(self):
        self.location = _make_location(location_id=9002)
        self.item = _make_eve_type(34, "Tritanium")

    def test_process_structure_orders_stores_buy_and_sell(self):
        page_data = [
            {
                "order_id": 1,
                "type_id": 34,
                "price": 5.5,
                "volume_remain": 100,
                "is_buy_order": True,
            },
            {
                "order_id": 2,
                "type_id": 34,
                "price": 6.0,
                "volume_remain": 50,
                "is_buy_order": False,
            },
        ]
        with patch("market.helpers.orders.EsiClient") as client_mock:
            client_mock.return_value.get_structure_market_orders_page.return_value = EsiResponse(
                response_code=200, data=page_data
            )
            created, volume = process_structure_sell_orders_page(
                1, self.location.location_id, 1, "task-uid"
            )

        self.assertEqual(2, created)
        self.assertEqual(150, volume)
        self.assertEqual(
            1, EveMarketItemOrder.objects.filter(is_buy_order=True).count()
        )
        self.assertEqual(
            1, EveMarketItemOrder.objects.filter(is_buy_order=False).count()
        )

    def test_sell_expectation_current_quantity_ignores_buy_orders(self):
        EveMarketItemOrder.objects.create(
            location=self.location,
            item=self.item,
            order_id=1,
            price=5,
            quantity=100,
            is_buy_order=True,
            imported_by_task_uid="uid",
        )
        EveMarketItemOrder.objects.create(
            location=self.location,
            item=self.item,
            order_id=2,
            price=6,
            quantity=50,
            is_buy_order=False,
            imported_by_task_uid="uid",
        )
        expectation = EveMarketItemExpectation.objects.create(
            item=self.item,
            location=self.location,
            quantity=10,
        )
        self.assertEqual(50, expectation.current_quantity)


class ContractMatchTestCase(TestCase):
    def setUp(self):
        self.fitting = EveFitting.objects.create(
            name="[FL33T] Sabre",
            eft_format="""[Sabre, [FL33T] Sabre]
Nanofiber Internal Structure II
Nanofiber Internal Structure II
125mm Gatling AutoCannon II
125mm Gatling AutoCannon II
125mm Gatling AutoCannon II
125mm Gatling AutoCannon II
125mm Gatling AutoCannon II
Hail S x2000
""",
            ship_id=22456,
        )
        _make_typed_eve_type(22456, "Sabre", 6, "Ship")
        _make_typed_eve_type(
            2605, "Nanofiber Internal Structure II", 7, "Module"
        )
        _make_typed_eve_type(2873, "125mm Gatling AutoCannon II", 7, "Module")
        _make_typed_eve_type(12608, "Hail S", 8, "Charge")

    def test_normalize_contract_items_aggregates_slots(self):
        raw = [
            {"type_id": 2873, "quantity": 1, "is_included": True},
            {"type_id": 2873, "quantity": 1, "is_included": True},
            {"type_id": 2873, "quantity": 1, "is_included": True},
        ]
        aggregated = normalize_contract_items(raw)
        self.assertEqual({2873: 3}, aggregated)

    def test_perfect_match_scores_one(self):
        contract_items = {
            22456: 1,
            2605: 2,
            2873: 5,
            12608: 2000,
        }
        score, missing, _ = score_contract_against_fitting(
            contract_items, self.fitting
        )
        self.assertEqual(1.0, score)
        self.assertEqual([], missing)
        self.assertTrue(is_match_accepted(score))

    def test_partial_match_below_threshold(self):
        contract_items = {
            22456: 1,
            2873: 2,
        }
        score, missing, _ = score_contract_against_fitting(
            contract_items, self.fitting
        )
        self.assertLess(score, MATCH_THRESHOLD)
        self.assertTrue(missing)

    def test_match_contract_picks_best_fitting(self):
        other = EveFitting.objects.create(
            name="[FL33T] Sabre v2",
            eft_format=self.fitting.eft_format.replace(
                "[FL33T] Sabre]", "[FL33T] Sabre v2]", 1
            ),
            ship_id=22456,
        )
        contract_items = {
            22456: 1,
            2605: 2,
            2873: 5,
            12608: 2000,
        }
        fitting, score, _, _ = match_contract_to_fitting(
            contract_items,
            [other, self.fitting],
            preferred_fitting=self.fitting,
        )
        self.assertEqual(self.fitting, fitting)
        self.assertEqual(1.0, score)

    def test_match_score_ignores_bulk_charges(self):
        contract_items = {
            22456: 1,
            2605: 2,
            2873: 5,
            12608: 50,
        }
        score, missing, _ = score_contract_against_fitting(
            contract_items, self.fitting
        )
        self.assertEqual(1.0, score)
        self.assertTrue(missing)

    def test_highest_percent_wins_close_fits(self):
        """Named Buffer only keeps when items match Buffer (not Active)."""
        _make_typed_eve_type(37604, "Apostle", 6, "Ship")
        _make_typed_eve_type(2048, "Damage Control II", 7, "Module")
        _make_typed_eve_type(
            41459, "Capital I-a Enduring Armor Repairer", 7, "Module"
        )
        _make_typed_eve_type(
            20245,
            "25000mm Crystalline Carbonide Restrained Plates",
            7,
            "Module",
        )
        _make_typed_eve_type(41490, "Armor Energizing Charge", 8, "Charge")

        active = EveFitting.objects.create(
            name="[FL33T] Active Apostle",
            ship_id=37604,
            eft_format="""[Apostle, [FL33T] Active Apostle]
Damage Control II
Capital I-a Enduring Armor Repairer
Armor Energizing Charge x1000
""",
        )
        buffer = EveFitting.objects.create(
            name="[FL33T] Buffer Apostle",
            ship_id=37604,
            eft_format="""[Apostle, [FL33T] Buffer Apostle]
Damage Control II
25000mm Crystalline Carbonide Restrained Plates
Armor Energizing Charge x1000
""",
        )
        location = _make_location(location_id=9105)
        buffer_contract = EveMarketContract.objects.create(
            id=50007,
            title="Buffer Apostle",
            price=1,
            issuer_external_id=1,
            status="outstanding",
            location=location,
            fitting=buffer,
            is_public=False,
        )
        # Active hull modules under a Buffer title → name matches, fit does not
        apply_content_match(
            buffer_contract,
            {37604: 1, 2048: 1, 41459: 1, 41490: 1000},
        )
        buffer_contract.refresh_from_db()
        self.assertIsNone(buffer_contract.fitting_id)
        self.assertLess(buffer_contract.match_score, MATCH_THRESHOLD)

        active_contract = EveMarketContract.objects.create(
            id=50008,
            title="Active Apostle",
            price=1,
            issuer_external_id=1,
            status="outstanding",
            location=location,
            fitting=active,
            is_public=False,
        )
        apply_content_match(
            active_contract,
            {37604: 1, 2048: 1, 41459: 1, 41490: 1000},
        )
        active_contract.refresh_from_db()
        self.assertEqual(active.id, active_contract.fitting_id)
        self.assertGreaterEqual(active_contract.match_score, MATCH_THRESHOLD)

    def test_apply_content_match_clears_fitting_below_threshold(self):
        location = _make_location(location_id=9101)
        contract = EveMarketContract.objects.create(
            id=50001,
            title=self.fitting.name,
            price=1,
            issuer_external_id=1,
            status="outstanding",
            location=location,
            fitting=self.fitting,
            is_public=False,
        )
        apply_content_match(contract, {22456: 1})
        contract.refresh_from_db()
        self.assertIsNone(contract.fitting_id)
        self.assertIsNotNone(contract.match_score)
        self.assertLess(contract.match_score, MATCH_THRESHOLD)

    def test_list_sync_does_not_overwrite_frozen_match(self):
        location = _make_location(location_id=9102)
        other = EveFitting.objects.create(
            name="[FL33T] Sabre Frozen Sync",
            eft_format=self.fitting.eft_format.replace(
                "[FL33T] Sabre]", "[FL33T] Sabre Frozen Sync]", 1
            ),
            ship_id=22456,
        )
        contract = EveMarketContract.objects.create(
            id=50002,
            title=other.name,
            price=1,
            issuer_external_id=1,
            status="outstanding",
            location=location,
            fitting=self.fitting,
            is_public=False,
            items_fetched=True,
            match_score=0.95,
        )
        db_contract = SimpleNamespace(
            contract_id=50002,
            type=EveMarketContract.esi_contract_type,
            start_location_id=location.location_id,
            title=other.name,
            status="outstanding",
            price=1,
            issuer_id=1,
            date_issued=timezone.now(),
            date_expired=timezone.now() + timedelta(days=7),
            date_completed=None,
            assignee_id=None,
            acceptor_id=None,
        )
        self.assertTrue(
            create_or_update_contract_from_db_contract(db_contract, location)
        )
        contract.refresh_from_db()
        self.assertEqual(self.fitting.id, contract.fitting_id)
        self.assertEqual(0.95, contract.match_score)

    def test_outstanding_stock_q_pending_and_verified(self):
        location = _make_location(location_id=9103)
        pending = EveMarketContract.objects.create(
            id=50003,
            title="pending",
            price=1,
            issuer_external_id=1,
            status="outstanding",
            location=location,
            fitting=self.fitting,
            items_fetched=False,
        )
        verified = EveMarketContract.objects.create(
            id=50004,
            title="verified",
            price=1,
            issuer_external_id=1,
            status="outstanding",
            location=location,
            fitting=self.fitting,
            items_fetched=True,
            match_score=0.9,
        )
        failed = EveMarketContract.objects.create(
            id=50005,
            title="failed",
            price=1,
            issuer_external_id=1,
            status="outstanding",
            location=location,
            fitting=self.fitting,
            items_fetched=True,
            match_score=0.5,
        )
        stock_ids = set(
            EveMarketContract.objects.filter(
                outstanding_stock_q()
            ).values_list("id", flat=True)
        )
        self.assertIn(pending.id, stock_ids)
        self.assertIn(verified.id, stock_ids)
        self.assertNotIn(failed.id, stock_ids)

    def test_nonsense_title_is_not_content_matched(self):
        """Wrong/missing title never assigns from contents alone."""
        location = _make_location(location_id=9104)
        _make_typed_eve_type(37604, "Apostle", 6, "Ship")
        _make_typed_eve_type(2048, "Damage Control II", 7, "Module")
        _make_typed_eve_type(
            20245,
            "25000mm Crystalline Carbonide Restrained Plates",
            7,
            "Module",
        )
        buffer = EveFitting.objects.create(
            name="[FL33T] Buffer Apostle",
            ship_id=37604,
            eft_format="""[Apostle, [FL33T] Buffer Apostle]
Damage Control II
25000mm Crystalline Carbonide Restrained Plates
""",
        )
        contract = EveMarketContract.objects.create(
            id=50006,
            title="totally wrong apostle name",
            price=1,
            issuer_external_id=1,
            status="outstanding",
            location=location,
            fitting=None,
            is_public=False,
        )
        apply_content_match(
            contract,
            {37604: 1, 2048: 1, 20245: 1},
        )
        contract.refresh_from_db()
        self.assertIsNone(contract.fitting_id)
        self.assertEqual(0.0, contract.match_score)

        named = EveMarketContract.objects.create(
            id=50009,
            title="Buffer Apostle",
            price=1,
            issuer_external_id=1,
            status="outstanding",
            location=location,
            fitting=buffer,
            is_public=False,
        )
        apply_content_match(named, {37604: 1, 2048: 1, 20245: 1})
        named.refresh_from_db()
        self.assertEqual(buffer.id, named.fitting_id)
        self.assertGreaterEqual(named.match_score, MATCH_THRESHOLD)


class SellOrderRowsTestCase(TestCase):
    def setUp(self):
        self.location = _make_location(location_id=9010)
        self.ammo_type = _make_eve_type(12773, "Fusion S")
        _make_typed_eve_type(19720, "Augoror", 6, "Ship")
        _make_typed_eve_type(2203, "Acolyte I", 8, "Charge")
        self.fitting = EveFitting.objects.create(
            name="[FL33T] Augoror",
            eft_format=(
                "[Augoror, [FL33T] Augoror]\n\n"
                "Light Missile Launcher II\n\n"
                "Acolyte I x50\n"
            ),
            ship_id=19720,
        )
        doctrine = EveDoctrine.objects.create(
            name="Test Doctrine",
            type=DOCTRINE_TYPE_NON_STRATEGIC,
            description="test",
        )
        doctrine.locations.add(self.location)
        EveDoctrineFitting.objects.create(
            doctrine=doctrine,
            fitting=self.fitting,
            role="primary",
        )

    def test_unified_sell_order_rows_merge_recommendations_and_stock(self):
        EveMarketContractExpectation.objects.create(
            location=self.location,
            fitting=self.fitting,
            quantity=1,
        )
        EveMarketItemOrder.objects.create(
            location=self.location,
            item=self.ammo_type,
            quantity=12,
            price=100,
            is_buy_order=False,
        )
        rows = {
            row["item_name"]: row
            for row in build_unified_sell_order_rows(self.location)
        }
        self.assertEqual(rows["Fusion S"]["current_qty"], 12)
        acolyte = rows["Acolyte I"]
        self.assertEqual(acolyte["current_qty"], 0)
        self.assertEqual(acolyte["desired_qty"], 50)
        self.assertEqual(acolyte["recommended_qty"], 50)
        self.assertIn("[FL33T] Augoror", acolyte["references"])
        self.assertIn("consumable", acolyte["sources"])
        self.assertTrue(acolyte["is_editable"])

        save_sell_order_desired_quantities(
            self.location,
            {f"desired_{acolyte['type_id']}": "75"},
        )
        rows = {
            row["item_name"]: row
            for row in build_unified_sell_order_rows(self.location)
        }
        self.assertEqual(rows["Acolyte I"]["desired_qty"], 75)
        self.assertTrue(rows["Acolyte I"]["is_pinned"])

    def test_recommended_qty_scales_with_contract_expectation_quantity(self):
        EveMarketContractExpectation.objects.create(
            location=self.location,
            fitting=self.fitting,
            quantity=3,
        )
        rows = {
            row["item_name"]: row
            for row in build_unified_sell_order_rows(self.location)
        }
        self.assertEqual(rows["Acolyte I"]["recommended_qty"], 150)

    def test_filter_search_and_stock_filters(self):
        rows = [
            {
                "item_name": "Acolyte I",
                "current_qty": 0,
                "desired_qty": 0,
                "recommended_qty": 50,
                "references": "[FL33T] Augoror",
                "sources": "consumable",
                "markup_pct": None,
            },
            {
                "item_name": "Fusion S",
                "current_qty": 0,
                "desired_qty": 100,
                "recommended_qty": 0,
                "references": "",
                "sources": "pinned",
                "markup_pct": 10,
            },
            {
                "item_name": "Augoror",
                "current_qty": 10,
                "desired_qty": 100,
                "recommended_qty": 0,
                "references": "[FL33T] Augoror",
                "sources": "non-doctrine ship",
                "markup_pct": -25,
            },
            {
                "item_name": "Damage Control II",
                "current_qty": 150,
                "desired_qty": 100,
                "recommended_qty": 0,
                "references": "[FL33T] Augoror",
                "sources": "fitting",
                "markup_pct": 25,
            },
            {
                "item_name": "Multispectrum Coating II",
                "current_qty": 30,
                "desired_qty": 100,
                "recommended_qty": 0,
                "references": "[FL33T] Augoror",
                "sources": "fitting",
                "markup_pct": 2,
            },
            {
                "item_name": "Overstocked Hull",
                "current_qty": 250,
                "desired_qty": 100,
                "recommended_qty": 0,
                "references": "[FL33T] Augoror",
                "sources": "non-doctrine ship",
                "markup_pct": 2,
            },
        ]

        search_rows = filter_sell_order_rows(rows, search="acolyte")
        self.assertEqual(
            [row["item_name"] for row in search_rows], ["Acolyte I"]
        )

        no_stock = filter_sell_order_rows(rows, stock_filter="no_stock")
        self.assertEqual(
            [row["item_name"] for row in no_stock],
            ["Fusion S"],
        )

        very_understocked = filter_sell_order_rows(
            rows, stock_filter="very_understocked"
        )
        self.assertEqual(
            [row["item_name"] for row in very_understocked],
            ["Augoror"],
        )

        understocked = filter_sell_order_rows(
            rows, stock_filter="understocked"
        )
        self.assertEqual(
            [row["item_name"] for row in understocked],
            ["Multispectrum Coating II"],
        )

        overstocked = filter_sell_order_rows(rows, stock_filter="overstocked")
        self.assertEqual(
            [row["item_name"] for row in overstocked],
            ["Damage Control II"],
        )

        very_overstocked = filter_sell_order_rows(
            rows, stock_filter="very_overstocked"
        )
        self.assertEqual(
            [row["item_name"] for row in very_overstocked],
            ["Overstocked Hull"],
        )

    def test_stock_level_uses_reasonable_qty_when_present(self):
        row = {
            "current_qty": 150,
            "reasonable_qty": 10,
            "desired_qty": 100,
        }
        self.assertEqual(_stock_level(row), "very_understocked")

        overstocked_row = {
            "current_qty": 250,
            "reasonable_qty": 150,
            "desired_qty": 100,
        }
        self.assertEqual(_stock_level(overstocked_row), "overstocked")

    def test_reasonable_listing_thresholds(self):
        self.assertTrue(
            _order_quantity_counts_as_reasonable(2_400_000, 2_000_000)
        )
        self.assertFalse(
            _order_quantity_counts_as_reasonable(2_400_001, 2_000_000)
        )
        self.assertTrue(_order_quantity_counts_as_reasonable(500_000, 50_000))
        self.assertTrue(_order_quantity_counts_as_reasonable(1_000_000, None))
        self.assertEqual(REASONABLE_MARKUP_MAX_PCT, 20)
        self.assertEqual(REASONABLE_JITA_PRICE_FLOOR, 1_000_000)

    def test_format_listed_qty_display(self):
        self.assertEqual(_format_listed_qty_display(11, 100), "11 (100)")
        self.assertEqual(_format_listed_qty_display(12, 12), "12")

    def test_reasonable_qty_excludes_overpriced_orders(self):
        EveMarketItemOrder.objects.filter(
            location=self.location, item=self.ammo_type
        ).delete()
        EveMarketItemOrder.objects.create(
            location=self.location,
            item=self.ammo_type,
            quantity=11,
            price=2_200_000,
            is_buy_order=False,
        )
        EveMarketItemOrder.objects.create(
            location=self.location,
            item=self.ammo_type,
            quantity=89,
            price=3_000_000,
            is_buy_order=False,
        )
        with patch(
            "market.helpers.sell_orders.get_prices_by_type_id",
            return_value={self.ammo_type.pk: 2_000_000},
        ), patch(
            "market.helpers.sell_orders.get_volume_90d_by_type_id",
            return_value={},
        ):
            rows = {
                row["item_name"]: row
                for row in build_unified_sell_order_rows(self.location)
            }
        fusion = rows["Fusion S"]
        self.assertEqual(fusion["current_qty"], 100)
        self.assertEqual(fusion["reasonable_qty"], 11)

        model_admin = LocationSellOrdersModelAdmin(EveType, admin.site)
        display = model_admin.display_current_qty(SellOrderListItem(fusion))
        self.assertEqual(display, "11 (100)")

    def test_filter_source_and_markup_filters(self):
        rows = [
            {
                "item_name": "Acolyte I",
                "current_qty": 0,
                "desired_qty": 0,
                "recommended_qty": 50,
                "references": "[FL33T] Augoror",
                "sources": "consumable",
                "markup_pct": -25,
            },
            {
                "item_name": "Augoror",
                "current_qty": 0,
                "desired_qty": 10,
                "recommended_qty": 0,
                "references": "[FL33T] Augoror",
                "sources": "non-doctrine ship",
                "markup_pct": -10,
            },
            {
                "item_name": "Refit Module",
                "current_qty": 0,
                "desired_qty": 0,
                "recommended_qty": 1,
                "references": "[FL33T] Augoror",
                "sources": "refit",
                "markup_pct": 2,
            },
            {
                "item_name": "Overpriced Module",
                "current_qty": 0,
                "desired_qty": 0,
                "recommended_qty": 0,
                "references": "",
                "sources": "fitting",
                "markup_pct": 25,
            },
            {
                "item_name": "Unknown Price",
                "current_qty": 0,
                "desired_qty": 0,
                "recommended_qty": 0,
                "references": "",
                "sources": "fitting",
                "markup_pct": None,
            },
        ]

        consumable_rows = filter_sell_order_rows(
            rows, source_filter="consumable"
        )
        self.assertEqual(
            [row["item_name"] for row in consumable_rows],
            ["Acolyte I"],
        )

        ship_rows = filter_sell_order_rows(
            rows, source_filter="non-doctrine ship"
        )
        self.assertEqual(
            [row["item_name"] for row in ship_rows],
            ["Augoror"],
        )

        refit_rows = filter_sell_order_rows(rows, source_filter="refit")
        self.assertEqual(
            [row["item_name"] for row in refit_rows],
            ["Refit Module"],
        )

        very_underpriced = filter_sell_order_rows(
            rows, markup_filter="very_underpriced"
        )
        self.assertEqual(
            [row["item_name"] for row in very_underpriced],
            ["Acolyte I"],
        )

        underpriced = filter_sell_order_rows(rows, markup_filter="underpriced")
        self.assertEqual(
            [row["item_name"] for row in underpriced],
            ["Augoror"],
        )

        normal = filter_sell_order_rows(rows, markup_filter="normal")
        self.assertEqual(
            [row["item_name"] for row in normal],
            ["Refit Module"],
        )

        very_overpriced = filter_sell_order_rows(
            rows, markup_filter="very_overpriced"
        )
        self.assertEqual(
            [row["item_name"] for row in very_overpriced],
            ["Overpriced Module"],
        )

        unknown_markup = filter_sell_order_rows(rows, markup_filter="normal")
        self.assertNotIn(
            "Unknown Price", [row["item_name"] for row in unknown_markup]
        )

    def test_fitting_expectation_tags_ship_hull_source(self):
        fitting = EveFitting.objects.create(
            name="[FL33T] Rifter",
            eft_format=rifter_eft("[FL33T] Rifter"),
            ship_id=587,
        )
        _make_typed_eve_type(587, "Rifter", 6, "Ship")
        EveMarketFittingExpectation.objects.create(
            fitting=fitting,
            location=self.location,
            quantity=5,
        )

        rows = {
            row["item_name"]: row
            for row in build_unified_sell_order_rows(self.location)
        }
        self.assertIn("non-doctrine ship", rows["Rifter"]["sources"])
        self.assertIn("fitting", rows["Damage Control II"]["sources"])
        self.assertNotIn(
            "non-doctrine ship", rows["Damage Control II"]["sources"]
        )

    def test_unreferenced_rows_hidden_by_default(self):
        rows = [
            {
                "item_name": "Acolyte I",
                "references": "[FL33T] Augoror",
                "sources": "consumable",
            },
            {
                "item_name": "Random Module",
                "references": "",
                "sources": "",
            },
        ]
        default_rows = filter_sell_order_rows(rows, hide_unreferenced=True)
        self.assertEqual(
            [row["item_name"] for row in default_rows], ["Acolyte I"]
        )

        search_rows = filter_sell_order_rows(
            rows, search="random", hide_unreferenced=False
        )
        self.assertEqual(
            [row["item_name"] for row in search_rows],
            ["Random Module"],
        )

        markup_rows = filter_sell_order_rows(
            rows,
            markup_filter="normal",
            hide_unreferenced=False,
        )
        self.assertEqual([row["item_name"] for row in markup_rows], [])

    def test_build_rows_skips_unreferenced_stock_when_not_requested(self):
        EveMarketItemOrder.objects.create(
            location=self.location,
            item=self.ammo_type,
            quantity=99,
            price=100,
            is_buy_order=False,
        )
        referenced_rows = build_unified_sell_order_rows(
            self.location,
            include_unreferenced=False,
        )
        all_rows = build_unified_sell_order_rows(
            self.location,
            include_unreferenced=True,
        )
        self.assertNotIn(
            "Fusion S",
            {row["item_name"] for row in referenced_rows},
        )
        self.assertIn(
            "Fusion S",
            {row["item_name"] for row in all_rows},
        )
        fusion_row = {row["item_name"]: row for row in all_rows}["Fusion S"]
        self.assertEqual(fusion_row["current_qty"], 99)

    def test_pricing_columns_use_lowest_sell_and_jita_markup(self):
        self.assertEqual(
            _format_reference_display(["Alpha"]),
            ("1 ship fits", "Alpha", ["Alpha"]),
        )
        self.assertEqual(
            _format_reference_display(["Alpha", "Beta", "Gamma"]),
            ("3 ship fits", "Alpha\nBeta\nGamma", ["Alpha", "Beta", "Gamma"]),
        )
        display, tooltip, names = _format_reference_display(
            ["Alpha", "Beta", "Gamma", "Delta"]
        )
        self.assertEqual(display, "4 ship fits")
        self.assertEqual(tooltip, "Alpha\nBeta\nGamma\nDelta")
        self.assertEqual(names, ["Alpha", "Beta", "Gamma", "Delta"])

        self.assertEqual(_calculate_markup_pct(115, 100), 15)
        self.assertIsNone(_calculate_markup_pct(None, 100))

        EveMarketItemOrder.objects.create(
            location=self.location,
            item=self.ammo_type,
            quantity=1,
            price=115,
            is_buy_order=False,
        )
        with patch(
            "market.helpers.sell_orders.get_prices_by_type_id",
            return_value={self.ammo_type.pk: 100},
        ), patch(
            "market.helpers.sell_orders.get_volume_90d_by_type_id",
            return_value={self.ammo_type.pk: 42_000},
        ):
            rows = {
                row["item_name"]: row
                for row in build_unified_sell_order_rows(self.location)
            }
        fusion = rows["Fusion S"]
        self.assertEqual(fusion["list_price"], 115)
        self.assertEqual(fusion["jita_sell_price"], 100)
        self.assertEqual(fusion["markup_pct"], 15)
        self.assertEqual(fusion["volume_90d"], 42_000)

    def test_volume_90d_sums_history_for_baseline_region(self):
        today = timezone.now().date()
        EveMarketItemHistory.objects.create(
            region_id=10000002,
            item=self.ammo_type,
            date=today - timedelta(days=10),
            average=1,
            highest=1,
            lowest=1,
            volume=1000,
        )
        EveMarketItemHistory.objects.create(
            region_id=10000002,
            item=self.ammo_type,
            date=today - timedelta(days=100),
            average=1,
            highest=1,
            lowest=1,
            volume=9999,
        )
        volumes = get_volume_90d_by_type_id([self.ammo_type.pk])
        self.assertEqual(volumes[self.ammo_type.pk], 1000)

    def test_sort_sell_order_rows_by_current_qty_and_markup(self):
        rows = [
            {
                "item_name": "A",
                "current_qty": 10,
                "reasonable_qty": 3,
                "markup_pct": 50,
            },
            {
                "item_name": "B",
                "current_qty": 2,
                "reasonable_qty": 2,
                "markup_pct": None,
            },
            {
                "item_name": "C",
                "current_qty": 25,
                "reasonable_qty": 15,
                "markup_pct": 10,
            },
        ]
        model_admin = LocationSellOrdersModelAdmin(EveType, admin.site)
        list_display = list(model_admin.get_list_display(None))

        by_qty = _sort_sell_order_rows(
            rows,
            list_display,
            model_admin,
            EveType,
            {"o": "1"},
        )
        self.assertEqual(
            [row["item_name"] for row in by_qty],
            ["B", "A", "C"],
        )

        by_markup_desc = _sort_sell_order_rows(
            rows,
            list_display,
            model_admin,
            EveType,
            {"o": "-7"},
        )
        self.assertEqual(
            [row["item_name"] for row in by_markup_desc],
            ["A", "C", "B"],
        )

    def test_pinned_item_name_shows_pin_icon(self):

        model_admin = LocationSellOrdersModelAdmin(EveType, admin.site)
        unpinned = SellOrderListItem(
            {
                "item_name": "Fusion S",
                "current_qty": 0,
                "desired_qty": 0,
                "recommended_qty": 0,
                "is_pinned": False,
            }
        )
        pinned = SellOrderListItem(
            {
                "item_name": "Acolyte I",
                "current_qty": 0,
                "desired_qty": 75,
                "recommended_qty": 50,
                "is_pinned": True,
            }
        )

        self.assertEqual(
            model_admin.display_item_name(unpinned),
            "Fusion S",
        )
        pinned_html = str(model_admin.display_item_name(pinned))
        self.assertIn("pinned-hover", pinned_html)
        self.assertIn("pinned-icon", pinned_html)
        self.assertIn("Acolyte I", pinned_html)
        self.assertIn("You set the target stock", pinned_html)


class ExpectationsAdminViewsTestCase(TestCase):
    def setUp(self):
        self.location = _make_location(
            location_id=9020,
            market_categories=[FittingTag.NANOGANG],
        )
        self.fitting = EveFitting.objects.create(
            name="[FL33T] Augoror",
            eft_format=(
                "[Augoror, [FL33T] Augoror]\n\n"
                "Light Missile Launcher II\n\n"
                "Acolyte I x50\n"
            ),
            ship_id=19720,
        )
        self.fitting.set_tag_slugs([FittingTag.NANOGANG], write_history=False)
        doctrine = EveDoctrine.objects.create(
            name="Test Doctrine",
            type=DOCTRINE_TYPE_NON_STRATEGIC,
            description="test",
        )
        doctrine.locations.add(self.location)
        EveDoctrineFitting.objects.create(
            doctrine=doctrine,
            fitting=self.fitting,
            role="primary",
        )
        self.doctrine = doctrine
        self.factory = RequestFactory()

    def test_fitting_expectations_lists_non_doctrine_fits(self):
        non_doctrine = EveFitting.objects.create(
            name="[FL33T] Rifter",
            eft_format=rifter_eft("[FL33T] Rifter"),
            ship_id=587,
        )
        non_doctrine.set_tag_slugs([FittingTag.NANOGANG], write_history=False)
        EveMarketFittingExpectation.objects.create(
            fitting=non_doctrine,
            location=self.location,
            quantity=4,
        )
        rows = build_fitting_expectation_rows(self.location)
        fitting_ids = {row["fitting_id"] for row in rows}
        self.assertNotIn(self.fitting.pk, fitting_ids)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["fitting_id"], non_doctrine.pk)
        self.assertEqual(rows[0]["quantity"], 4)

        request = self.factory.get("/")
        context = build_location_fitting_expectations_context(
            self.location, request
        )
        self.assertEqual(context["total_row_count"], 1)
        self.assertEqual(
            context["cl"].result_list[0].fitting_name, non_doctrine.name
        )

    def test_contract_expectations_lists_doctrine_fits(self):
        EveMarketContractExpectation.objects.create(
            fitting=self.fitting,
            location=self.location,
            quantity=7,
        )
        rows = build_contract_expectation_rows(self.location)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["fitting_id"], self.fitting.pk)
        self.assertEqual(rows[0]["quantity"], 7)

        request = self.factory.get("/")
        context = build_location_contract_expectations_context(
            self.location, request
        )
        self.assertEqual(context["total_row_count"], 1)
        self.assertEqual(context["cl"].result_list[0].quantity, 7)

    def test_save_expectation_quantities_from_post_data(self):
        non_doctrine = EveFitting.objects.create(
            name="[FL33T] Rifter",
            eft_format=rifter_eft("[FL33T] Rifter"),
            ship_id=587,
        )
        save_fitting_expectation_quantities(
            self.location,
            {f"quantity_{non_doctrine.pk}": "6"},
        )
        save_contract_expectation_quantities(
            self.location,
            {f"quantity_{self.fitting.pk}": "9"},
        )
        self.assertEqual(
            EveMarketFittingExpectation.objects.get(
                location=self.location, fitting=non_doctrine
            ).quantity,
            6,
        )
        self.assertEqual(
            EveMarketContractExpectation.objects.get(
                location=self.location, fitting=self.fitting
            ).quantity,
            9,
        )

    def test_fitting_expectations_save_on_page_two(self):
        fittings = []
        for i in range(2):
            fitting = EveFitting.objects.create(
                name=f"[FL33T] Rifter {i:02d}",
                eft_format=rifter_eft(f"[FL33T] Rifter {i:02d}"),
                ship_id=587,
            )
            fitting.set_tag_slugs([FittingTag.NANOGANG], write_history=False)
            fittings.append(fitting)

        with patch(
            "market.helpers.expectations_changelist."
            "LocationFittingExpectationsModelAdmin.list_per_page",
            1,
        ):
            get_request = self.factory.get("/", {"p": "2"})
            context = build_location_fitting_expectations_context(
                self.location, get_request
            )
            self.assertEqual(context["cl"].page_num, 2)
            self.assertIn("p=2", context["form_action"])
            page2_fitting_id = context["cl"].result_list[0].fitting_id
            self.assertEqual(_allowed_fitting_ids(context), {page2_fitting_id})

            user = get_user_model().objects.create_superuser(
                username="expectations-admin",
                email="admin@example.com",
                password="test-pass",
            )
            url = reverse(
                "admin:market_location_fitting_expectations",
                args=[self.location.pk],
            )
            post_request = self.factory.post(
                f"{url}?p=2",
                {f"quantity_{page2_fitting_id}": "8"},
            )
            post_request.user = user
            post_request.session = {}
            setattr(post_request, "_messages", FallbackStorage(post_request))

            response = market_location_fitting_expectations_view(
                post_request, self.location.pk
            )
            self.assertEqual(response.status_code, 302)
            self.assertIn("p=2", response.url)

        self.assertEqual(
            EveMarketFittingExpectation.objects.get(
                location=self.location, fitting_id=page2_fitting_id
            ).quantity,
            8,
        )

    def test_contract_expectations_include_all_doctrine_fittings(self):
        other_doctrine = EveDoctrine.objects.create(
            name="Other Doctrine",
            type=DOCTRINE_TYPE_NON_STRATEGIC,
            description="other",
        )
        other_fitting = EveFitting.objects.create(
            name="[FL33T] Other Ship",
            eft_format=rifter_eft("[FL33T] Other Ship"),
            ship_id=587,
        )
        EveDoctrineFitting.objects.create(
            doctrine=other_doctrine,
            fitting=other_fitting,
            role="primary",
        )

        rows = build_contract_expectation_rows(self.location)
        fitting_names = [row["fitting_name"] for row in rows]
        self.assertIn(self.fitting.name, fitting_names)
        self.assertIn(other_fitting.name, fitting_names)
        self.assertEqual(len(rows), 2)

    def test_fitting_expectation_filters(self):
        non_doctrine = EveFitting.objects.create(
            name="[FL33T] Rifter",
            eft_format=rifter_eft("[FL33T] Rifter"),
            ship_id=587,
        )
        non_doctrine.set_tag_slugs([FittingTag.NANOGANG], write_history=False)
        rows = build_fitting_expectation_rows(self.location)
        EveMarketFittingExpectation.objects.create(
            fitting=non_doctrine,
            location=self.location,
            quantity=3,
        )
        rows = build_fitting_expectation_rows(self.location)

        by_tag = filter_fitting_expectation_rows(
            rows,
            tag_filter=FittingTag.NANOGANG,
        )
        self.assertEqual(len(by_tag), 1)
        self.assertEqual(by_tag[0]["fitting_id"], non_doctrine.pk)

        by_configured = filter_fitting_expectation_rows(
            rows,
            configured_filter="yes",
        )
        self.assertEqual(len(by_configured), 1)
        self.assertEqual(by_configured[0]["quantity"], 3)

        by_unconfigured = filter_fitting_expectation_rows(
            rows,
            configured_filter="no",
        )
        self.assertEqual(by_unconfigured, [])

    def test_contract_expectation_filters(self):
        rows = build_contract_expectation_rows(self.location)
        EveMarketContractExpectation.objects.create(
            fitting=self.fitting,
            location=self.location,
            quantity=10,
        )
        rows = build_contract_expectation_rows(self.location)
        by_search = filter_contract_expectation_rows(rows, search="augoror")
        self.assertEqual(len(by_search), 1)
        self.assertEqual(by_search[0]["fitting_id"], self.fitting.pk)

        by_doctrine = filter_contract_expectation_rows(
            rows,
            doctrine_filters=[str(self.doctrine.pk)],
        )
        self.assertEqual(len(by_doctrine), 1)
        self.assertEqual(by_doctrine[0]["fitting_id"], self.fitting.pk)

    def test_contract_expectation_multi_doctrine_filters(self):
        other_doctrine = EveDoctrine.objects.create(
            name="Other Doctrine",
            type=DOCTRINE_TYPE_NON_STRATEGIC,
            description="other",
        )
        other_fitting = EveFitting.objects.create(
            name="[FL33T] Other Ship",
            eft_format=rifter_eft("[FL33T] Other Ship"),
            ship_id=587,
        )
        EveDoctrineFitting.objects.create(
            doctrine=other_doctrine,
            fitting=other_fitting,
            role="primary",
        )
        rows = build_contract_expectation_rows(self.location)
        self.assertEqual(len(rows), 2)

        by_one_doctrine = filter_contract_expectation_rows(
            rows,
            doctrine_filters=[str(self.doctrine.pk)],
        )
        self.assertEqual(len(by_one_doctrine), 1)
        self.assertEqual(by_one_doctrine[0]["fitting_id"], self.fitting.pk)

        by_both_doctrines = filter_contract_expectation_rows(
            rows,
            doctrine_filters=[str(self.doctrine.pk), str(other_doctrine.pk)],
        )
        self.assertEqual(len(by_both_doctrines), 2)
        fitting_ids = {row["fitting_id"] for row in by_both_doctrines}
        self.assertEqual(fitting_ids, {self.fitting.pk, other_fitting.pk})

        request = self.factory.get(
            "/",
            {
                "doctrine": [str(self.doctrine.pk), str(other_doctrine.pk)],
            },
        )
        context = build_location_contract_expectations_context(
            self.location, request
        )
        self.assertEqual(context["filtered_row_count"], 2)
        self.assertEqual(len(context["cl"].result_list), 2)


class MismatchedContractsViewsTestCase(TestCase):
    def setUp(self):
        self.location = _make_location(location_id=9021)
        self.fitting = EveFitting.objects.create(
            name="[FL33T] Augoror",
            eft_format=(
                "[Augoror, [FL33T] Augoror]\n\nLight Missile Launcher II\n"
            ),
            ship_id=19720,
        )

    def test_attention_page_lists_only_subperfect_matches(self):
        EveMarketContract.objects.create(
            id=1001,
            status="outstanding",
            title="Perfect fit",
            price=1,
            issuer_external_id=1,
            location=self.location,
            fitting=self.fitting,
            match_score=1.0,
            match_is_flagged=False,
            is_public=True,
        )
        EveMarketContract.objects.create(
            id=1002,
            status="outstanding",
            title="Wrong modules",
            price=1,
            issuer_external_id=2,
            location=self.location,
            fitting=self.fitting,
            match_score=0.85,
            match_is_flagged=True,
            is_public=False,
        )
        EveMarketContract.objects.create(
            id=1003,
            status="finished",
            title="Old contract",
            price=1,
            issuer_external_id=3,
            location=self.location,
            fitting=self.fitting,
            match_score=0.5,
            match_is_flagged=True,
        )

        context = build_location_contracts_context(self.location)
        self.assertEqual(context["attention_count"], 1)
        self.assertEqual(len(context["attention_rows"]), 1)
        self.assertEqual(
            context["attention_rows"][0]["title"], "Wrong modules"
        )
        self.assertEqual(context["attention_rows"][0]["match_score"], 0.85)
        self.assertEqual(context["attention_rows"][0]["match_percent"], "85%")
        self.assertEqual(context["attention_rows"][0]["contract_id"], 1002)


class ContractItemsFetchTestCase(TestCase):
    def setUp(self):
        self.location = _make_location(location_id=9010)

    def test_empty_successful_fetch_marks_items_fetched(self):
        contract = EveMarketContract.objects.create(
            id=88001,
            location=self.location,
            title="Empty hull",
            price=1,
            status="outstanding",
            issuer_external_id=1,
            is_public=True,
        )
        with patch("market.helpers.contract_items.EsiClient") as client_mock:
            client_mock.return_value.get_public_contract_items.return_value = (
                EsiResponse(response_code=200, data=[])
            )
            self.assertTrue(fetch_and_match_contract_items(contract.pk))

        contract.refresh_from_db()
        self.assertTrue(contract.items_fetched)
