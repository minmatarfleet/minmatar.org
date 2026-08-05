"""Tests for LP store offer economics (admin price tracking)."""

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.db import ProgrammingError
from django.test import RequestFactory, TestCase
from django.utils import timezone
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

from industry.admin import (
    IndustryLpStoreCurrencyListFilter,
    IndustryLpStoreExcludeChipsFilter,
    IndustryLpStoreExcludeSupplyPackagesFilter,
    IndustryLpStoreExcludeTagsFilter,
    IndustryLpStoreOfferAdmin,
)
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
IMPERIAL_CORP_ID = 1000179
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
        # Cost/Profit are offer acquisition, not shared planner build cost.
        self.assertEqual(econ.cost_per_unit, 100_000_000)
        self.assertEqual(econ.profit_vs_sell, 150_000_000)
        self.assertEqual(econ.isk_per_lp, 800.0)
        self.assertEqual(econ.acquisition_isk_per_unit, 100_000_000)
        # Other cost includes SDE manufacturing BOM (1× LP Input Item @ 1.5M).
        self.assertEqual(econ.other_cost, 1_500_000)
        # (250M - 20M - 1.5M) / 100k LP = 2285
        self.assertAlmostEqual(econ.conversion_isk_per_lp_sell, 2285.0)
        self.assertAlmostEqual(econ.conversion_isk_per_lp_buy, 2285.0)

    @patch(
        "industry.helpers.lp_store_economics.plan_product_unit_cost",
        return_value=type(
            "U",
            (),
            {"cost_per": 180_000_000},
        )(),
    )
    def test_blueprint_offers_differ_by_acquisition(self, mock_plan):
        """Same hull BPC with different LP/ISK → different Cost/Profit."""
        cheap = IndustryLpStoreOffer.objects.create(
            offer_id=1010,
            corporation_id=TLIB_CORP_ID,
            type_id=BPC_TYPE_ID,
            lp_cost=40_000,
            isk_cost=0,
            quantity=1,
        )
        dear = IndustryLpStoreOffer.objects.create(
            offer_id=1011,
            corporation_id=TLIB_CORP_ID,
            type_id=BPC_TYPE_ID,
            lp_cost=40_000,
            isk_cost=10_000_000,
            quantity=1,
        )
        rows = offer_economics_for_queryset([cheap, dear])
        mock_plan.assert_called()
        cheap_econ = rows[cheap.pk]
        dear_econ = rows[dear.pk]
        self.assertEqual(cheap_econ.build_cost_per_unit, 180_000_000)
        self.assertEqual(dear_econ.build_cost_per_unit, 180_000_000)
        # (40k*800 + 0) / 1 = 32M; (40k*800 + 10M) / 1 = 42M
        self.assertEqual(cheap_econ.cost_per_unit, 32_000_000)
        self.assertEqual(dear_econ.cost_per_unit, 42_000_000)
        self.assertEqual(cheap_econ.profit_vs_sell, 218_000_000)
        self.assertEqual(dear_econ.profit_vs_sell, 208_000_000)
        self.assertNotEqual(cheap_econ.cost_per_unit, dear_econ.cost_per_unit)
        # Conversion subtracts BOM (1.5M); acquisition does not.
        # cheap: (250M - 0 - 1.5M) / 40k = 6212.5
        self.assertAlmostEqual(cheap_econ.conversion_isk_per_lp_sell, 6212.5)
        self.assertEqual(cheap_econ.other_cost, 1_500_000)

    def test_blueprint_pack_multiplies_build_materials_in_other_cost(self):
        """Fuzzwork scales Materials to build by offer quantity."""
        pack = IndustryLpStoreOffer.objects.create(
            offer_id=1012,
            corporation_id=TLIB_CORP_ID,
            type_id=BPC_TYPE_ID,
            lp_cost=100_000,
            isk_cost=100_000_000,
            quantity=10,
        )
        with patch(
            "industry.helpers.lp_store_economics.plan_product_unit_cost",
            return_value=type("U", (), {"cost_per": 180_000_000})(),
        ):
            econ = offer_economics_for_queryset([pack])[pack.pk]
        # 10 runs × 1 input @ 1.5M
        self.assertEqual(econ.other_cost, 15_000_000)
        # (250M * 10 - 100M - 15M) / 100k = 23850
        self.assertAlmostEqual(econ.conversion_isk_per_lp_sell, 23850.0)
        # Acquisition ignores BOM: (100k*800 + 100M) / 10 = 18M
        self.assertEqual(econ.acquisition_isk_per_unit, 18_000_000)

    def test_volume_windows_sum_daily_history(self):
        today = timezone.now().date()
        EveMarketItemHistory.objects.filter(item=self.input_type).delete()
        EveMarketItemHistory.objects.create(
            region_id=JITA_REGION_ID,
            item=self.input_type,
            date=today - timedelta(days=0),
            average=Decimal("1500000"),
            highest=Decimal("1600000"),
            lowest=Decimal("1400000"),
            order_count=1,
            volume=10,
        )
        EveMarketItemHistory.objects.create(
            region_id=JITA_REGION_ID,
            item=self.input_type,
            date=today - timedelta(days=3),
            average=Decimal("1500000"),
            highest=Decimal("1600000"),
            lowest=Decimal("1400000"),
            order_count=1,
            volume=20,
        )
        EveMarketItemHistory.objects.create(
            region_id=JITA_REGION_ID,
            item=self.input_type,
            date=today - timedelta(days=20),
            average=Decimal("1500000"),
            highest=Decimal("1600000"),
            lowest=Decimal("1400000"),
            order_count=1,
            volume=40,
        )
        offer = IndustryLpStoreOffer.objects.get(offer_id=1002)
        econ = offer_economics_for_queryset([offer])[offer.pk]
        self.assertEqual(econ.volume_1d, 10)
        self.assertEqual(econ.volume_7d, 30)
        self.assertEqual(econ.volume_30d, 70)

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

    @patch(
        "industry.helpers.lp_store_economics.IndustryLpStoreOfferRequiredItem.objects"
    )
    def test_missing_required_items_table_still_computes(self, mock_req):
        mock_req.filter.side_effect = ProgrammingError("no such table")
        offer = IndustryLpStoreOffer.objects.get(offer_id=1002)
        rows = offer_economics_for_queryset([offer])
        self.assertIn(offer.pk, rows)
        self.assertEqual(rows[offer.pk].type_name, "LP Input Item")
        self.assertEqual(rows[offer.pk].required_items_summary, "")
        self.assertEqual(rows[offer.pk].other_cost, 0)


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
        self.assertIn(f'Title="Type {INPUT_TYPE_ID}"'.lower(), html.lower())
        self.assertNotIn("input ·", html)
        self.assertNotIn(f"type {INPUT_TYPE_ID}", html)
        self.assertIn("lp-store-offer-item__name", html)
        self.assertIn("/icon?size=32", html)

    def test_type_name_display_uses_bp_icon_for_blueprints(self):
        # pylint: disable=protected-access
        IndustryLpStoreOfferAdmin._request_stash = {
            self.offer.pk: SimpleNamespace(
                kind="blueprint",
                type_id=32312,
                type_name="Typhoon Fleet Issue Blueprint",
                market_type_id=17740,
                market_type_name="Typhoon Fleet Issue",
            )
        }
        try:
            html = str(self.admin.type_name_display(self.offer))
        finally:
            IndustryLpStoreOfferAdmin._request_stash = None
        self.assertIn("Typhoon Fleet Issue (BPC)", html)
        self.assertIn("/bp?size=32", html)
        self.assertNotIn("blueprint ·", html)

    def test_type_name_display_falls_back_to_eve_type(self):
        # pylint: disable=protected-access
        IndustryLpStoreOfferAdmin._request_stash = None
        html = str(self.admin.type_name_display(self.offer))
        self.assertIn("LP Input Item", html)
        self.assertIn(f'Title="Type {INPUT_TYPE_ID}"'.lower(), html.lower())
        self.assertNotIn(f"type {INPUT_TYPE_ID}", html)

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

    def test_search_respects_currency_filter(self):
        """Name search must not reintroduce offers from other currencies."""
        IndustryLoyaltyPoint.objects.update_or_create(
            corporation_id=IMPERIAL_CORP_ID,
            defaults={
                "name": "24th Imperial Crusade",
                "default_isk_per_lp": 800,
                "is_active": True,
            },
        )
        IndustryLpStoreOffer.objects.create(
            offer_id=2003,
            corporation_id=IMPERIAL_CORP_ID,
            type_id=INPUT_TYPE_ID,
            lp_cost=2000,
            isk_cost=100_000,
            quantity=1,
        )
        request = self.factory.get(
            "/admin/industry/industrylpstoreoffer/",
            {"q": "LP Input", "currency": str(TLIB_CORP_ID)},
        )
        request.user = self.user
        qs = self.admin.get_queryset(request)
        # Django 5.2 SimpleListFilter stores params[name][-1].
        currency_filter = IndustryLpStoreCurrencyListFilter(
            request,
            {"currency": [str(TLIB_CORP_ID)]},
            IndustryLpStoreOffer,
            self.admin,
        )
        qs = currency_filter.queryset(request, qs)
        self.assertEqual(list(qs.values_list("offer_id", flat=True)), [2001])
        result, _ = self.admin.get_search_results(request, qs, "LP Input")
        self.assertEqual(
            list(result.values_list("offer_id", flat=True)), [2001]
        )
        self.assertEqual(
            list(result.values_list("corporation_id", flat=True)),
            [TLIB_CORP_ID],
        )

    def test_list_display_fuzzwork_column_order(self):
        self.assertNotIn("kind_display", self.admin.list_display)
        self.assertNotIn("ak_cost", self.admin.list_display)
        self.assertNotIn("volume_90d_display", self.admin.list_display)
        # Fuzzwork conversion rates only — not acquisition / buyback columns.
        self.assertNotIn("isk_per_lp_display", self.admin.list_display)
        self.assertNotIn("cost_display", self.admin.list_display)
        self.assertNotIn("profit_vs_sell_display", self.admin.list_display)
        self.assertEqual(self.admin.list_display[0], "type_name_display")
        # Market prices before conversion rates (Fuzzwork-like).
        sell_i = self.admin.list_display.index("jita_sell_display")
        conv_i = self.admin.list_display.index("conversion_sell_display")
        self.assertLess(sell_i, conv_i)
        self.assertIn("conversion_buy_display", self.admin.list_display)
        self.assertIn("volume_1d_display", self.admin.list_display)
        self.assertIn("volume_7d_display", self.admin.list_display)
        self.assertIn("volume_30d_display", self.admin.list_display)

    def test_lp_cost_column_is_sortable(self):
        self.assertEqual(
            self.admin.lp_cost_display.admin_order_field, "lp_cost"
        )
        request = self.factory.get("/admin/industry/industrylpstoreoffer/")
        request.user = self.user
        qs = self.admin.get_queryset(request)
        ordered = list(
            qs.order_by("lp_cost").values_list("offer_id", flat=True)
        )
        self.assertEqual(ordered, [2001])

    def test_exclude_supply_packages_hides_required_package_offers(self):
        """BPC output + Supply Package required item → excluded."""
        misc = EveGroup.objects.create(
            id=314,
            name="Miscellaneous",
            published=True,
            eve_category=EveCategory.objects.get(id=6),
        )
        package = EveType.objects.create(
            id=93609,
            name="Imperial War Reserves Supply Package",
            published=True,
            eve_group=misc,
        )
        clean = IndustryLpStoreOffer.objects.create(
            offer_id=2100,
            corporation_id=TLIB_CORP_ID,
            type_id=INPUT_TYPE_ID,
            lp_cost=40_000,
            isk_cost=0,
            quantity=1,
        )
        with_pkg = IndustryLpStoreOffer.objects.create(
            offer_id=2101,
            corporation_id=TLIB_CORP_ID,
            type_id=INPUT_TYPE_ID,
            lp_cost=100_000,
            isk_cost=100_000_000,
            quantity=10,
        )
        IndustryLpStoreOfferRequiredItem.objects.create(
            offer=with_pkg,
            type_id=package.id,
            quantity=3,
        )
        # Output itself is a supply package.
        package_offer = IndustryLpStoreOffer.objects.create(
            offer_id=2102,
            corporation_id=TLIB_CORP_ID,
            type_id=package.id,
            lp_cost=5_000,
            isk_cost=0,
            quantity=1,
        )
        request = self.factory.get("/admin/industry/industrylpstoreoffer/")
        request.user = self.user
        yes = IndustryLpStoreExcludeSupplyPackagesFilter(
            request,
            {"exclude_supply_packages": "1"},
            IndustryLpStoreOffer,
            self.admin,
        )
        yes_ids = set(
            yes.queryset(
                request, self.admin.get_queryset(request)
            ).values_list("offer_id", flat=True)
        )
        self.assertIn(clean.offer_id, yes_ids)
        self.assertIn(self.offer.offer_id, yes_ids)
        self.assertNotIn(with_pkg.offer_id, yes_ids)
        self.assertNotIn(package_offer.offer_id, yes_ids)

        no = IndustryLpStoreExcludeSupplyPackagesFilter(
            request,
            {"exclude_supply_packages": "0"},
            IndustryLpStoreOffer,
            self.admin,
        )
        no_ids = set(
            no.queryset(request, self.admin.get_queryset(request)).values_list(
                "offer_id", flat=True
            )
        )
        self.assertNotIn(clean.offer_id, no_ids)
        self.assertIn(with_pkg.offer_id, no_ids)
        self.assertIn(package_offer.offer_id, no_ids)
        self.assertEqual(
            yes.lookups(request, self.admin), (("1", "Yes"), ("0", "No"))
        )

    def test_exclude_tags_hides_required_tag_offers(self):
        tags_group = EveGroup.objects.create(
            id=370,
            name="Criminal Tags",
            published=True,
            eve_category=EveCategory.objects.get(id=6),
        )
        tag = EveType.objects.create(
            id=17226,
            name="Domination Gold Tag",
            published=True,
            eve_group=tags_group,
        )
        clean = IndustryLpStoreOffer.objects.create(
            offer_id=2200,
            corporation_id=TLIB_CORP_ID,
            type_id=INPUT_TYPE_ID,
            lp_cost=1_000,
            isk_cost=0,
            quantity=1,
        )
        with_tag = IndustryLpStoreOffer.objects.create(
            offer_id=2201,
            corporation_id=TLIB_CORP_ID,
            type_id=INPUT_TYPE_ID,
            lp_cost=2_000,
            isk_cost=0,
            quantity=1,
        )
        IndustryLpStoreOfferRequiredItem.objects.create(
            offer=with_tag,
            type_id=tag.id,
            quantity=2,
        )
        tag_offer = IndustryLpStoreOffer.objects.create(
            offer_id=2202,
            corporation_id=TLIB_CORP_ID,
            type_id=tag.id,
            lp_cost=500,
            isk_cost=0,
            quantity=1,
        )
        request = self.factory.get("/admin/industry/industrylpstoreoffer/")
        request.user = self.user
        yes = IndustryLpStoreExcludeTagsFilter(
            request, {"exclude_tags": "1"}, IndustryLpStoreOffer, self.admin
        )
        yes_ids = set(
            yes.queryset(
                request, self.admin.get_queryset(request)
            ).values_list("offer_id", flat=True)
        )
        self.assertIn(clean.offer_id, yes_ids)
        self.assertNotIn(with_tag.offer_id, yes_ids)
        self.assertNotIn(tag_offer.offer_id, yes_ids)

        no = IndustryLpStoreExcludeTagsFilter(
            request, {"exclude_tags": "0"}, IndustryLpStoreOffer, self.admin
        )
        no_ids = set(
            no.queryset(request, self.admin.get_queryset(request)).values_list(
                "offer_id", flat=True
            )
        )
        self.assertNotIn(clean.offer_id, no_ids)
        self.assertIn(with_tag.offer_id, no_ids)
        self.assertIn(tag_offer.offer_id, no_ids)
        self.assertEqual(
            yes.lookups(request, self.admin), (("1", "Yes"), ("0", "No"))
        )

    def test_exclude_chips_hides_required_and_output_chip_offers(self):
        """Nexus Chip as required item or output → excluded; implants stay."""
        misc = EveGroup.objects.create(
            id=315,
            name="Miscellaneous",
            published=True,
            eve_category=EveCategory.objects.get(id=6),
        )
        chip = EveType.objects.create(
            id=17816,
            name="Minmatar UUB Nexus Chip",
            published=True,
            eve_group=misc,
        )
        # Social Adaptation Chip must NOT match Nexus Chip detection.
        implant = EveType.objects.create(
            id=9956,
            name="Social Adaptation Chip - Basic",
            published=True,
            eve_group=misc,
        )
        clean = IndustryLpStoreOffer.objects.create(
            offer_id=2300,
            corporation_id=TLIB_CORP_ID,
            type_id=INPUT_TYPE_ID,
            lp_cost=1_000,
            isk_cost=0,
            quantity=1,
        )
        with_chip = IndustryLpStoreOffer.objects.create(
            offer_id=2301,
            corporation_id=TLIB_CORP_ID,
            type_id=INPUT_TYPE_ID,
            lp_cost=2_000,
            isk_cost=0,
            quantity=1,
        )
        IndustryLpStoreOfferRequiredItem.objects.create(
            offer=with_chip,
            type_id=chip.id,
            quantity=4,
        )
        chip_offer = IndustryLpStoreOffer.objects.create(
            offer_id=2302,
            corporation_id=TLIB_CORP_ID,
            type_id=chip.id,
            lp_cost=500,
            isk_cost=0,
            quantity=1,
        )
        implant_offer = IndustryLpStoreOffer.objects.create(
            offer_id=2303,
            corporation_id=TLIB_CORP_ID,
            type_id=implant.id,
            lp_cost=800,
            isk_cost=0,
            quantity=1,
        )
        request = self.factory.get("/admin/industry/industrylpstoreoffer/")
        request.user = self.user
        yes = IndustryLpStoreExcludeChipsFilter(
            request, {"exclude_chips": "1"}, IndustryLpStoreOffer, self.admin
        )
        yes_ids = set(
            yes.queryset(
                request, self.admin.get_queryset(request)
            ).values_list("offer_id", flat=True)
        )
        self.assertIn(clean.offer_id, yes_ids)
        self.assertIn(implant_offer.offer_id, yes_ids)
        self.assertNotIn(with_chip.offer_id, yes_ids)
        self.assertNotIn(chip_offer.offer_id, yes_ids)

        no = IndustryLpStoreExcludeChipsFilter(
            request, {"exclude_chips": "0"}, IndustryLpStoreOffer, self.admin
        )
        no_ids = set(
            no.queryset(request, self.admin.get_queryset(request)).values_list(
                "offer_id", flat=True
            )
        )
        self.assertNotIn(clean.offer_id, no_ids)
        self.assertNotIn(implant_offer.offer_id, no_ids)
        self.assertIn(with_chip.offer_id, no_ids)
        self.assertIn(chip_offer.offer_id, no_ids)
        self.assertEqual(
            yes.lookups(request, self.admin), (("1", "Yes"), ("0", "No"))
        )

    @patch("industry.admin.offer_economics_for_queryset")
    def test_changelist_renders_names_before_stash_clear(self, mock_econ):
        """Regression: TemplateResponse must render while stash is live."""
        mock_econ.return_value = {
            self.offer.pk: SimpleNamespace(
                kind="input",
                type_id=INPUT_TYPE_ID,
                type_name="LP Input Item",
                market_type_id=INPUT_TYPE_ID,
                market_type_name="LP Input Item",
                currency_name="Tribal Liberation Force",
                required_items_summary="",
                other_cost=0,
                jita_sell=1_000_000,
                jita_buy=900_000,
                conversion_isk_per_lp_sell=500.0,
                conversion_isk_per_lp_buy=400.0,
                volume_1d=100,
                volume_7d=700,
                volume_30d=3_000,
                isk_per_lp=800.0,
                cost_per_unit=800_000,
                profit_vs_sell=200_000,
            )
        }
        request = self.factory.get("/admin/industry/industrylpstoreoffer/")
        request.user = self.user
        response = self.admin.changelist_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(getattr(response, "is_rendered", False))
        content = response.content.decode()
        self.assertIn("LP Input Item", content)
        self.assertIn("Tribal Liberation Force", content)
        self.assertIn("1,000,000", content)
        self.assertIn("500.0", content)
        # Stash cleared after render.
        # pylint: disable=protected-access
        self.assertIsNone(IndustryLpStoreOfferAdmin._request_stash)

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
        self.assertNotIn("isk_per_lp_display", self.admin.list_display)
        self.assertNotIn("cost_display", self.admin.list_display)
        self.assertNotIn("profit_vs_sell_display", self.admin.list_display)
        self.assertIn("volume_1d_display", self.admin.list_display)
        self.assertIn("volume_7d_display", self.admin.list_display)
        self.assertIn("volume_30d_display", self.admin.list_display)
        self.assertNotIn("volume_90d_display", self.admin.list_display)

    @patch(
        "industry.admin.offer_economics_for_queryset",
        return_value={},
    )
    def test_changelist_uses_sticky_item_template(self, mock_econ):
        request = self.factory.get("/admin/industry/industrylpstoreoffer/")
        request.user = self.user
        response = self.admin.changelist_view(request)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("position: sticky", content)
        self.assertIn("field-type_name_display", content)
        self.assertIn(
            "admin/industry/industrylpstoreoffer/change_list.html",
            self.admin.change_list_template,
        )
