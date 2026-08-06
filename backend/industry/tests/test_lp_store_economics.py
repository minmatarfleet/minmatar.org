"""Tests for LP store offer economics helpers."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.db import ProgrammingError
from django.test import TestCase
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

from industry.helpers.lp_store_economics import (
    NEGLIGIBLE_LP_FORGE_VOLUME_30D,
    LpStoreOfferEconomics,
    bpc_type_id_to_product_type_id,
    offer_economics_for_queryset,
    offer_is_below_set_lp_price,
    offer_pks_below_set_lp_price,
    offer_type_ids_with_viable_forge_volume,
    tracked_corporation_ids,
)
from industry.helpers.plan_costing import ItemPlanCost
from industry.helpers.lp_store_useless import (
    USELESS_BELOW_MEDIAN_RATIO,
    USELESS_MAX_RELATIVE_SPREAD,
    USELESS_MIN_ISK_FROM_STOCKPILE,
    USELESS_STOCKPILE_LP_HIGH,
    USELESS_STOCKPILE_LP_LOW,
    CurrencyPeerStats,
    offer_fails_below_peer_average,
    offer_fails_profit,
    offer_fails_stockpile_usefulness,
    offer_fails_volume_or_volatility,
    offer_is_useless,
    peer_stats_by_corporation,
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


def _fake_mfg_plan(
    *,
    materials_isk: int = 40_000_000,
    jobs_isk: int = 5_000_000,
    taxes_isk: int = 5_000_000,
    quantity: int = 1,
) -> ItemPlanCost:
    mfg = materials_isk + jobs_isk + taxes_isk
    return ItemPlanCost(
        type_id=HULL_TYPE_ID,
        name="Republic Fleet Firetail",
        kind="Navy",
        output_quantity=quantity,
        materials_jita_sell_isk=materials_isk,
        total_job_costs_isk=jobs_isk,
        taxes_isk=taxes_isk,
        manufacturing_isk=mfg,
        manufacturing_cost_per_isk=int(round(mfg / quantity)),
        cost_per_isk=180_000_000,
    )


def _amamake_mock_return(batch_sizes=(1,)):
    plans = {}
    for batch in batch_sizes:
        plans[(HULL_TYPE_ID, batch)] = _fake_mfg_plan(
            materials_isk=40_000_000 * batch,
            jobs_isk=5_000_000 * batch,
            taxes_isk=5_000_000 * batch,
            quantity=batch,
        )
    return {HULL_TYPE_ID: 180_000_000}, plans


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
        "industry.helpers.lp_store_economics._amamake_manufacturing_costs",
        return_value=_amamake_mock_return(),
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
        # Other cost = Amamake manufacturing (excl. navy BPC LP, no alliance freight).
        self.assertEqual(econ.other_cost, 50_000_000)
        self.assertEqual(econ.input_cost_isk, 70_000_000)
        self.assertEqual(econ.input_freight_isk, 1_200_000)
        # Net after 3.37% tax + Red Frog in/out freight.
        self.assertAlmostEqual(econ.conversion_isk_per_lp_sell, 1628.75)
        self.assertAlmostEqual(econ.conversion_isk_per_lp_buy, 1628.75)
        self.assertEqual(econ.jita_avg_7d, 250_000_000)
        self.assertAlmostEqual(econ.conversion_isk_per_lp_avg_7d, 1628.75)

    @patch(
        "industry.helpers.lp_store_economics._amamake_manufacturing_costs",
        return_value=_amamake_mock_return(),
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
        self.assertAlmostEqual(cheap_econ.conversion_isk_per_lp_sell, 4571.875)
        self.assertEqual(cheap_econ.other_cost, 50_000_000)

    def test_blueprint_pack_multiplies_amamake_mfg_in_other_cost(self):
        """Amamake manufacturing cost scales by offer quantity."""
        pack = IndustryLpStoreOffer.objects.create(
            offer_id=1012,
            corporation_id=TLIB_CORP_ID,
            type_id=BPC_TYPE_ID,
            lp_cost=100_000,
            isk_cost=100_000_000,
            quantity=10,
        )
        with patch(
            "industry.helpers.lp_store_economics._amamake_manufacturing_costs",
            return_value=_amamake_mock_return(batch_sizes=(1, 10)),
        ):
            econ = offer_economics_for_queryset([pack])[pack.pk]
        # 10 runs × 50M Amamake mfg / hull
        self.assertEqual(econ.other_cost, 500_000_000)
        self.assertAlmostEqual(econ.conversion_isk_per_lp_sell, 17287.5)
        # Acquisition ignores build: (100k*800 + 100M) / 10 = 18M
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

    def test_offer_type_ids_viable_volume_uses_hull_for_bpc(self):
        """Navy BPC offers are viable when the hull has 30d Forge volume."""
        # History in setUp is on hull / input / req — not on BPC itself.
        viable = offer_type_ids_with_viable_forge_volume(
            [BPC_TYPE_ID, INPUT_TYPE_ID, 999001]
        )
        self.assertIn(BPC_TYPE_ID, viable)
        self.assertIn(INPUT_TYPE_ID, viable)
        self.assertNotIn(999001, viable)
        self.assertGreaterEqual(NEGLIGIBLE_LP_FORGE_VOLUME_30D, 1)

    def test_offer_type_ids_viable_volume_excludes_below_threshold(self):
        dead = EveType.objects.create(
            id=42426,
            name="Dead LP Item",
            published=True,
            eve_group=self.hull.eve_group,
        )
        EveMarketItemHistory.objects.create(
            region_id=JITA_REGION_ID,
            item=dead,
            date=timezone.now().date() - timedelta(days=2),
            average=Decimal("100"),
            highest=Decimal("100"),
            lowest=Decimal("100"),
            order_count=0,
            volume=0,
        )
        viable = offer_type_ids_with_viable_forge_volume(
            [dead.id],
            min_volume_30d=1,
        )
        self.assertNotIn(dead.id, viable)

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
        # Net after tax + Red Frog output freight (no input freight).
        self.assertAlmostEqual(econ.conversion_isk_per_lp_sell, 904.45)
        self.assertEqual(econ.input_cost_isk, 500_000)
        self.assertEqual(econ.input_freight_isk, 0)

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
        self.assertAlmostEqual(econ.conversion_isk_per_lp_sell, 394.725)
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
        self.assertAlmostEqual(econ.conversion_isk_per_lp_sell, 1372.6)
        self.assertAlmostEqual(econ.conversion_isk_per_lp_buy, 436.3)

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

    def test_offer_is_below_set_lp_price_vs_buyback(self):
        """Null or conversion < default_isk_per_lp is below set; equal is not."""
        offer = IndustryLpStoreOffer.objects.get(offer_id=1002)
        # History average 1.5M → net ~904.45; buyback 800.
        econ = offer_economics_for_queryset([offer])[offer.pk]
        self.assertAlmostEqual(econ.conversion_isk_per_lp_sell, 904.45)
        self.assertEqual(econ.isk_per_lp, 800.0)
        self.assertFalse(offer_is_below_set_lp_price(econ))

        # Force below via high ISK cost → net 100.
        below = IndustryLpStoreOffer.objects.create(
            offer_id=1050,
            corporation_id=TLIB_CORP_ID,
            type_id=INPUT_TYPE_ID,
            lp_cost=1_000,
            isk_cost=1_304_450,
            quantity=1,
        )
        below_econ = offer_economics_for_queryset([below])[below.pk]
        self.assertAlmostEqual(below_econ.conversion_isk_per_lp_sell, 100.0)
        self.assertTrue(offer_is_below_set_lp_price(below_econ))

        # Exact equality is at/above set price.
        equal = IndustryLpStoreOffer.objects.create(
            offer_id=1051,
            corporation_id=TLIB_CORP_ID,
            type_id=INPUT_TYPE_ID,
            lp_cost=1_000,
            isk_cost=604_450,
            quantity=1,
        )
        equal_econ = offer_economics_for_queryset([equal])[equal.pk]
        self.assertAlmostEqual(equal_econ.conversion_isk_per_lp_sell, 800.0)
        self.assertFalse(offer_is_below_set_lp_price(equal_econ))

        # No market price → null conversion → below set.
        dead = EveType.objects.create(
            id=42499,
            name="Unpriced LP Cosmetic",
            published=True,
            eve_group=EveGroup.objects.get(id=27),
        )
        null_offer = IndustryLpStoreOffer.objects.create(
            offer_id=1052,
            corporation_id=TLIB_CORP_ID,
            type_id=dead.id,
            lp_cost=1_000,
            isk_cost=0,
            quantity=1,
        )
        null_econ = offer_economics_for_queryset([null_offer])[null_offer.pk]
        self.assertIsNone(null_econ.conversion_isk_per_lp_sell)
        self.assertTrue(offer_is_below_set_lp_price(null_econ))
        below_pks = offer_pks_below_set_lp_price(
            [offer, below, equal, null_offer]
        )
        self.assertNotIn(offer.pk, below_pks)
        self.assertIn(below.pk, below_pks)
        self.assertNotIn(equal.pk, below_pks)
        self.assertIn(null_offer.pk, below_pks)


def _econ(**overrides) -> LpStoreOfferEconomics:
    """Minimal viable economics row; override fields under test."""
    base = {
        "pk": 1,
        "offer_id": 1,
        "corporation_id": TLIB_CORP_ID,
        "type_id": INPUT_TYPE_ID,
        "type_name": "Test Offer",
        "currency_name": "Tribal Liberation Force",
        "isk_per_lp": 800.0,
        "lp_cost": 1_000,
        "isk_cost": 0,
        "ak_cost": 0,
        "quantity": 1,
        "required_items_summary": "",
        "other_cost": 0,
        "input_cost_isk": 0,
        "input_freight_isk": 0,
        "acquisition_isk_per_unit": 800_000,
        "market_type_id": INPUT_TYPE_ID,
        "market_type_name": "Test Offer",
        "jita_sell": 2_000_000,
        "jita_buy": 1_900_000,
        "jita_avg_7d": 1_950_000,
        "conversion_isk_per_lp_sell": 2_000.0,
        "conversion_isk_per_lp_buy": 1_900.0,
        "conversion_isk_per_lp_avg_7d": 1_950.0,
        "volume_1d": 100,
        "volume_7d": 700,
        "volume_30d": 10_000,
        "build_cost_per_unit": None,
        "cost_per_unit": 800_000,
        "kind": "input",
        "profit_vs_sell": 1_200_000,
    }
    base.update(overrides)
    return LpStoreOfferEconomics(**base)


class OfferIsUselessHelperTestCase(TestCase):
    def test_stockpile_unaffordable_from_high_band(self):
        econ = _econ(lp_cost=USELESS_STOCKPILE_LP_HIGH + 1)
        self.assertTrue(offer_fails_stockpile_usefulness(econ))
        self.assertTrue(offer_is_useless(econ))

    def test_stockpile_trivial_isk_from_low_dump(self):
        econ = _econ(conversion_isk_per_lp_sell=100.0, volume_30d=1_000_000)
        self.assertTrue(offer_fails_stockpile_usefulness(econ))
        self.assertLess(
            100.0 * USELESS_STOCKPILE_LP_LOW, USELESS_MIN_ISK_FROM_STOCKPILE
        )

    def test_stockpile_liquidity_exceeds_30d_volume(self):
        econ = _econ(lp_cost=1_000, quantity=1, volume_30d=50)
        self.assertTrue(offer_fails_stockpile_usefulness(econ))

    def test_stockpile_useful_passes(self):
        econ = _econ(
            lp_cost=1_000,
            conversion_isk_per_lp_sell=2_000.0,
            volume_30d=50_000,
        )
        self.assertFalse(offer_fails_stockpile_usefulness(econ))

    def test_profit_null_conversion(self):
        self.assertTrue(
            offer_fails_profit(_econ(conversion_isk_per_lp_sell=None))
        )

    def test_profit_at_or_below_buyback(self):
        self.assertTrue(
            offer_fails_profit(_econ(conversion_isk_per_lp_sell=800.0))
        )
        self.assertTrue(
            offer_fails_profit(_econ(conversion_isk_per_lp_sell=500.0))
        )
        self.assertFalse(
            offer_fails_profit(_econ(conversion_isk_per_lp_sell=801.0))
        )

    def test_profit_acquisition_ge_jita_sell(self):
        econ = _econ(
            conversion_isk_per_lp_sell=2_000.0,
            acquisition_isk_per_unit=2_000_000,
            jita_sell=2_000_000,
        )
        self.assertTrue(offer_fails_profit(econ))

    def test_below_peer_median_ratio(self):
        peers = CurrencyPeerStats(
            median_conversion_sell=2_000.0, viable_count=5
        )
        floor = USELESS_BELOW_MEDIAN_RATIO * 2_000.0
        self.assertTrue(
            offer_fails_below_peer_average(
                _econ(conversion_isk_per_lp_sell=floor - 1), peers
            )
        )
        self.assertFalse(
            offer_fails_below_peer_average(
                _econ(conversion_isk_per_lp_sell=floor), peers
            )
        )
        self.assertFalse(
            offer_fails_below_peer_average(
                _econ(conversion_isk_per_lp_sell=2_000.0), None
            )
        )

    def test_volume_missing_or_negligible(self):
        self.assertTrue(
            offer_fails_volume_or_volatility(_econ(volume_30d=None))
        )
        self.assertTrue(
            offer_fails_volume_or_volatility(
                _econ(volume_30d=NEGLIGIBLE_LP_FORGE_VOLUME_30D - 1)
            )
        )
        self.assertFalse(
            offer_fails_volume_or_volatility(
                _econ(volume_30d=NEGLIGIBLE_LP_FORGE_VOLUME_30D)
            )
        )

    def test_volatility_missing_buy_or_wide_spread(self):
        self.assertTrue(offer_fails_volume_or_volatility(_econ(jita_buy=None)))
        sell = 1_000_000
        buy = int(sell * (1.0 - USELESS_MAX_RELATIVE_SPREAD - 0.1))
        self.assertTrue(
            offer_fails_volume_or_volatility(
                _econ(jita_sell=sell, jita_buy=buy)
            )
        )
        tight_buy = int(sell * 0.95)
        self.assertFalse(
            offer_fails_volume_or_volatility(
                _econ(jita_sell=sell, jita_buy=tight_buy)
            )
        )

    def test_offer_is_useless_combined_or(self):
        peers = CurrencyPeerStats(
            median_conversion_sell=2_000.0, viable_count=3
        )
        self.assertFalse(offer_is_useless(_econ(), peers))
        weak = _econ(conversion_isk_per_lp_sell=1_000.0)
        self.assertTrue(offer_is_useless(weak, peers))
        self.assertTrue(offer_fails_below_peer_average(weak, peers))
        self.assertFalse(offer_fails_profit(weak))

    def test_peer_stats_median_among_volume_viable(self):
        economics = {
            1: _econ(pk=1, conversion_isk_per_lp_sell=1_000.0, volume_30d=10),
            2: _econ(pk=2, conversion_isk_per_lp_sell=2_000.0, volume_30d=10),
            3: _econ(pk=3, conversion_isk_per_lp_sell=3_000.0, volume_30d=10),
            4: _econ(
                pk=4, conversion_isk_per_lp_sell=9_999.0, volume_30d=None
            ),
        }
        stats = peer_stats_by_corporation(economics)
        self.assertEqual(stats[TLIB_CORP_ID].median_conversion_sell, 2_000.0)
        self.assertEqual(stats[TLIB_CORP_ID].viable_count, 3)
