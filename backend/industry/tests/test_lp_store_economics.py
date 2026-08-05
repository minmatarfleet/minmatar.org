"""Tests for LP store offer economics (admin price tracking)."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from eveonline.models import EveLocation
from eveuniverse.models import (
    EveCategory,
    EveGroup,
    EveIndustryActivityDuration,
    EveIndustryActivityMaterial,
    EveIndustryActivityProduct,
    EveType,
)
from market.models import EveMarketItemHistory, EveMarketItemLocationPrice

from industry.admin import IndustryLpStoreOfferAdmin
from industry.helpers.lp_store_economics import (
    bpc_type_id_to_product_type_id,
    offer_economics_for_queryset,
    tracked_corporation_ids,
)
from industry.helpers.loyalty_store import sync_loyalty_store_offers
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLpStoreOffer,
    IndustryLpStoreOfferRequiredItem,
    IndustryProduct,
    Strategy,
)

TLIB_CORP_ID = 1000182
UNTRACKED_CORP_ID = 9999999
HULL_TYPE_ID = 17740
BPC_TYPE_ID = 32312
INPUT_TYPE_ID = 42424
REQ_TYPE_ID = 42425
JITA_REGION_ID = 10000002


class LpStoreEconomicsHelperTestCase(TestCase):
    def setUp(self):
        self.jita = EveLocation.objects.create(
            location_id=60003760,
            location_name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            solar_system_id=30000142,
            solar_system_name="Jita",
            short_name="Jita",
            region_id=JITA_REGION_ID,
            price_baseline=True,
            prices_active=True,
        )
        IndustryLoyaltyPoint.objects.update_or_create(
            corporation_id=TLIB_CORP_ID,
            defaults={
                "name": "Tribal Liberation Force",
                "default_isk_per_lp": 800,
                "is_active": True,
            },
        )
        IndustryLoyaltyPoint.objects.exclude(
            corporation_id=TLIB_CORP_ID
        ).update(is_active=False)

        category = EveCategory.objects.create(
            id=6, name="Ship", published=True
        )
        group = EveGroup.objects.create(
            id=27, name="Battleship", published=True, eve_category=category
        )
        self.hull = EveType.objects.create(
            id=HULL_TYPE_ID,
            name="Typhoon Fleet Issue",
            published=True,
            eve_group=group,
        )
        self.bpc = EveType.objects.create(
            id=BPC_TYPE_ID,
            name="Typhoon Fleet Issue Blueprint",
            published=True,
            eve_group=group,
        )
        self.input_type = EveType.objects.create(
            id=INPUT_TYPE_ID,
            name="LP Input Item",
            published=True,
            eve_group=group,
        )
        self.req_type = EveType.objects.create(
            id=REQ_TYPE_ID,
            name="LP Required Tag",
            published=True,
            eve_group=group,
        )
        EveIndustryActivityProduct.objects.create(
            eve_type=self.bpc,
            activity_id=1,
            product_eve_type=self.hull,
            quantity=1,
        )
        EveIndustryActivityDuration.objects.create(
            eve_type=self.bpc, activity_id=1, time=100
        )
        EveIndustryActivityMaterial.objects.create(
            eve_type=self.bpc,
            activity_id=1,
            material_eve_type=self.input_type,
            quantity=1,
        )

        with patch(
            "industry.tasks.ensure_loyalty_store_offers_for_product_task.delay"
        ):
            IndustryProduct.objects.create(
                eve_type=self.hull, strategy=Strategy.IMPORTED
            )

        sync_loyalty_store_offers(
            corporation_ids=[TLIB_CORP_ID, UNTRACKED_CORP_ID],
            offers=[
                {
                    "offer_id": 1001,
                    "corporation_id": TLIB_CORP_ID,
                    "type_id": BPC_TYPE_ID,
                    "lp_cost": 100_000,
                    "isk_cost": 20_000_000,
                    "quantity": 1,
                    "required_items": [],
                },
                {
                    "offer_id": 1002,
                    "corporation_id": TLIB_CORP_ID,
                    "type_id": INPUT_TYPE_ID,
                    "lp_cost": 1_000,
                    "isk_cost": 500_000,
                    "quantity": 1,
                    "required_items": [],
                },
                {
                    "offer_id": 1003,
                    "corporation_id": UNTRACKED_CORP_ID,
                    "type_id": INPUT_TYPE_ID,
                    "lp_cost": 1_000,
                    "isk_cost": 100_000,
                    "quantity": 1,
                    "required_items": [],
                },
                {
                    "offer_id": 1004,
                    "corporation_id": TLIB_CORP_ID,
                    "type_id": INPUT_TYPE_ID,
                    "lp_cost": 2_000,
                    "isk_cost": 100_000,
                    "quantity": 1,
                    "required_items": [
                        {"type_id": REQ_TYPE_ID, "quantity": 2}
                    ],
                },
            ],
            enqueue_history=False,
        )

        EveMarketItemHistory.objects.create(
            region_id=JITA_REGION_ID,
            item=self.hull,
            date=date(2026, 7, 30),
            average=Decimal("250000000"),
            highest=Decimal("260000000"),
            lowest=Decimal("240000000"),
            order_count=10,
            volume=5,
        )
        EveMarketItemHistory.objects.create(
            region_id=JITA_REGION_ID,
            item=self.input_type,
            date=date(2026, 7, 30),
            average=Decimal("1500000"),
            highest=Decimal("1600000"),
            lowest=Decimal("1400000"),
            order_count=20,
            volume=100,
        )
        EveMarketItemHistory.objects.create(
            region_id=JITA_REGION_ID,
            item=self.req_type,
            date=date(2026, 7, 30),
            average=Decimal("250000"),
            highest=Decimal("260000"),
            lowest=Decimal("240000"),
            order_count=5,
            volume=50,
        )

    def test_tracked_corporation_ids_active_only(self):
        self.assertEqual(tracked_corporation_ids(), [TLIB_CORP_ID])

    def test_bpc_maps_to_navy_product(self):
        mapping = bpc_type_id_to_product_type_id()
        self.assertEqual(mapping[BPC_TYPE_ID], HULL_TYPE_ID)

    @patch(
        "industry.helpers.lp_store_economics.plan_product_unit_cost",
        return_value=type(
            "U",
            (),
            {"cost_per": 180_000_000},
        )(),
    )
    def test_blueprint_row_uses_hull_market_and_build_cost(self, mock_plan):
        offer = IndustryLpStoreOffer.objects.get(offer_id=1001)
        rows = offer_economics_for_queryset([offer])
        mock_plan.assert_called()
        econ = rows[offer.pk]
        self.assertEqual(econ.kind, "blueprint")
        self.assertEqual(econ.market_type_id, HULL_TYPE_ID)
        self.assertEqual(econ.jita_sell, 250_000_000)
        self.assertEqual(econ.jita_buy, 250_000_000)
        self.assertEqual(econ.build_cost_per_unit, 180_000_000)
        self.assertEqual(econ.cost_per_unit, 180_000_000)
        self.assertEqual(econ.profit_vs_sell, 70_000_000)
        self.assertEqual(econ.isk_per_lp, 800.0)
        self.assertEqual(econ.acquisition_isk_per_unit, 100_000_000)
        # (250M - 20M) / 100k LP = 2300
        self.assertAlmostEqual(econ.conversion_isk_per_lp_sell, 2300.0)
        self.assertAlmostEqual(econ.conversion_isk_per_lp_buy, 2300.0)

    def test_input_row_uses_acquisition_and_own_type(self):
        offer = IndustryLpStoreOffer.objects.get(offer_id=1002)
        rows = offer_economics_for_queryset([offer])
        econ = rows[offer.pk]
        self.assertEqual(econ.kind, "input")
        self.assertEqual(econ.market_type_id, INPUT_TYPE_ID)
        self.assertEqual(econ.jita_sell, 1_500_000)
        self.assertEqual(econ.jita_buy, 1_500_000)
        self.assertIsNone(econ.build_cost_per_unit)
        self.assertEqual(econ.acquisition_isk_per_unit, 1_300_000)
        self.assertEqual(econ.cost_per_unit, 1_300_000)
        self.assertEqual(econ.profit_vs_sell, 200_000)
        # (1.5M - 0.5M) / 1000 = 1000
        self.assertAlmostEqual(econ.conversion_isk_per_lp_sell, 1000.0)

    def test_required_items_add_other_cost_to_conversion(self):
        offer = IndustryLpStoreOffer.objects.get(offer_id=1004)
        self.assertEqual(
            IndustryLpStoreOfferRequiredItem.objects.filter(
                offer=offer
            ).count(),
            1,
        )
        rows = offer_economics_for_queryset([offer])
        econ = rows[offer.pk]
        self.assertEqual(econ.other_cost, 500_000)  # 2 * 250k
        self.assertIn("LP Required Tag x2", econ.required_items_summary)
        # (1.5M - 100k - 500k) / 2000 = 450
        self.assertAlmostEqual(econ.conversion_isk_per_lp_sell, 450.0)
        # acquisition: (2000*800 + 100k + 500k) / 1 = 2.2M
        self.assertEqual(econ.acquisition_isk_per_unit, 2_200_000)

    def test_location_price_distinguishes_buy_and_sell(self):
        EveMarketItemLocationPrice.objects.create(
            location=self.jita,
            item=self.input_type,
            sell_price=Decimal("2000000"),
            buy_price=Decimal("1000000"),
            split_price=Decimal("1500000"),
        )
        offer = IndustryLpStoreOffer.objects.get(offer_id=1002)
        rows = offer_economics_for_queryset([offer])
        econ = rows[offer.pk]
        self.assertEqual(econ.jita_sell, 2_000_000)
        self.assertEqual(econ.jita_buy, 1_000_000)
        # sell: (2M - 0.5M) / 1000 = 1500; buy: (1M - 0.5M) / 1000 = 500
        self.assertAlmostEqual(econ.conversion_isk_per_lp_sell, 1500.0)
        self.assertAlmostEqual(econ.conversion_isk_per_lp_buy, 500.0)

    def test_untracked_corp_offer_still_computes_but_admin_filters(self):
        offer = IndustryLpStoreOffer.objects.get(offer_id=1003)
        rows = offer_economics_for_queryset([offer])
        self.assertIn(offer.pk, rows)
        self.assertEqual(rows[offer.pk].corporation_id, UNTRACKED_CORP_ID)


class LpStoreOfferAdminTestCase(TestCase):
    def setUp(self):
        IndustryLoyaltyPoint.objects.update_or_create(
            corporation_id=TLIB_CORP_ID,
            defaults={
                "name": "Tribal Liberation Force",
                "default_isk_per_lp": 800,
                "is_active": True,
            },
        )
        IndustryLoyaltyPoint.objects.exclude(
            corporation_id=TLIB_CORP_ID
        ).update(is_active=False)
        category = EveCategory.objects.create(
            id=6, name="Ship", published=True
        )
        group = EveGroup.objects.create(
            id=27, name="Battleship", published=True, eve_category=category
        )
        self.input_type = EveType.objects.create(
            id=INPUT_TYPE_ID,
            name="LP Input Item",
            published=True,
            eve_group=group,
        )
        self.offer = IndustryLpStoreOffer.objects.create(
            offer_id=2001,
            corporation_id=TLIB_CORP_ID,
            type_id=INPUT_TYPE_ID,
            lp_cost=1000,
            isk_cost=500_000,
            quantity=1,
        )
        IndustryLpStoreOffer.objects.create(
            offer_id=2002,
            corporation_id=UNTRACKED_CORP_ID,
            type_id=INPUT_TYPE_ID,
            lp_cost=1000,
            isk_cost=100_000,
            quantity=1,
        )
        self.site = AdminSite()
        self.admin = IndustryLpStoreOfferAdmin(IndustryLpStoreOffer, self.site)
        self.factory = RequestFactory()
        user_model = get_user_model()
        self.user = user_model.objects.create_superuser(
            username="lp-admin",
            email="lp-admin@example.com",
            password="test",
        )

    def test_queryset_filters_to_tracked_corps(self):
        request = self.factory.get("/admin/industry/industrylpstoreoffer/")
        request.user = self.user
        qs = self.admin.get_queryset(request)
        self.assertEqual(list(qs.values_list("offer_id", flat=True)), [2001])

    def test_list_display_omits_type_id_column(self):
        self.assertNotIn("type_id", self.admin.list_display)
        self.assertIn("type_name_display", self.admin.list_display)

    def test_type_name_display_includes_name_and_type_id(self):
        # pylint: disable=protected-access
        IndustryLpStoreOfferAdmin._request_stash = {
            self.offer.pk: SimpleNamespace(
                kind="input",
                type_id=INPUT_TYPE_ID,
                type_name="LP Input Item",
                market_type_id=INPUT_TYPE_ID,
                market_type_name="LP Input Item",
            )
        }
        try:
            html = str(self.admin.type_name_display(self.offer))
        finally:
            IndustryLpStoreOfferAdmin._request_stash = None
        self.assertIn("LP Input Item", html)
        self.assertIn(f"type {INPUT_TYPE_ID}", html)
        self.assertIn("lp-store-offer-item__name", html)

    def test_search_by_type_name(self):
        request = self.factory.get(
            "/admin/industry/industrylpstoreoffer/",
            {"q": "LP Input"},
        )
        request.user = self.user
        qs = self.admin.get_queryset(request)
        result, _ = self.admin.get_search_results(request, qs, "LP Input")
        self.assertEqual(
            list(result.values_list("offer_id", flat=True)), [2001]
        )

    @patch(
        "industry.admin.offer_economics_for_queryset",
        return_value={},
    )
    def test_changelist_includes_price_columns(self, mock_econ):
        request = self.factory.get("/admin/industry/industrylpstoreoffer/")
        request.user = self.user
        response = self.admin.changelist_view(request)
        mock_econ.assert_called()
        self.assertEqual(response.status_code, 200)
        self.assertIn("jita_sell_display", self.admin.list_display)
        self.assertIn("jita_buy_display", self.admin.list_display)
        self.assertIn("conversion_sell_display", self.admin.list_display)
        self.assertIn("conversion_buy_display", self.admin.list_display)
        self.assertIn("cost_display", self.admin.list_display)

    @patch(
        "industry.admin.offer_economics_for_queryset",
        return_value={},
    )
    def test_changelist_uses_sticky_item_template(self, mock_econ):
        request = self.factory.get("/admin/industry/industrylpstoreoffer/")
        request.user = self.user
        response = self.admin.changelist_view(request)
        self.assertEqual(response.status_code, 200)
        response.render()
        content = response.content.decode()
        self.assertIn("position: sticky", content)
        self.assertIn("field-type_name_display", content)
        self.assertIn(
            "admin/industry/industrylpstoreoffer/change_list.html",
            self.admin.change_list_template,
        )
