"""Tests for hourly LP store offer economics snapshot rebuild."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from eveonline.models import EveLocation
from eveuniverse.models import EveCategory, EveGroup, EveType
from market.models import EveMarketItemHistory

from industry.helpers.lp_store_offer_economics_rebuild import (
    rebuild_lp_store_offer_economics,
)
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLpStoreOffer,
    IndustryLpStoreOfferEconomics,
)

TLIB_CORP_ID = 1000182
HULL_TYPE_ID = 17740
JITA_REGION_ID = 10000002

_AMAMAKE_PATCH = patch(
    "industry.helpers.lp_store_economics._amamake_manufacturing_costs",
    return_value=({}, {}),
)


class LpStoreOfferEconomicsRebuildTestCase(TestCase):
    def setUp(self):
        EveLocation.objects.create(
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
        category = EveCategory.objects.create(
            id=6, name="Ship", published=True
        )
        group = EveGroup.objects.create(
            id=27, name="Frigate", published=True, eve_category=category
        )
        self.hull = EveType.objects.create(
            id=HULL_TYPE_ID,
            name="Republic Fleet Firetail",
            published=True,
            eve_group=group,
        )
        today = timezone.now().date()
        EveMarketItemHistory.objects.create(
            region_id=JITA_REGION_ID,
            item=self.hull,
            date=today - timedelta(days=1),
            average=Decimal("250000000"),
            highest=Decimal("260000000"),
            lowest=Decimal("240000000"),
            order_count=5,
            volume=20,
        )
        self.offer = IndustryLpStoreOffer.objects.create(
            offer_id=3001,
            corporation_id=TLIB_CORP_ID,
            type_id=HULL_TYPE_ID,
            lp_cost=40_000,
            isk_cost=1_000_000,
            quantity=1,
        )

    def test_rebuild_writes_snapshot_rows(self):
        with _AMAMAKE_PATCH:
            count = rebuild_lp_store_offer_economics()
        self.assertEqual(count, 1)
        row = IndustryLpStoreOfferEconomics.objects.get(offer=self.offer)
        self.assertEqual(row.esi_offer_id, 3001)
        self.assertEqual(row.corporation_id, TLIB_CORP_ID)
        self.assertIn("Firetail", row.type_name)
        self.assertEqual(row.currency_name, "Tribal Liberation Force")
        self.assertEqual(row.lp_cost, 40_000)
        self.assertIsNotNone(row.jita_sell)
        self.assertIsNotNone(row.jita_avg_7d)
        self.assertIsNotNone(row.conversion_isk_per_lp_avg_7d)
        self.assertIsNotNone(row.rebuilt_at)
        self.assertFalse(row.involves_skin)

    def test_rebuild_marks_skin_offers(self):
        skins_cat = EveCategory.objects.create(
            id=91, name="SKINs", published=True
        )
        skin_group = EveGroup.objects.create(
            id=1950,
            name="Permanent SKIN",
            published=True,
            eve_category=skins_cat,
        )
        skin = EveType.objects.create(
            id=57016,
            name="Omen Navy Issue Penumbral Shadows SKIN",
            published=True,
            eve_group=skin_group,
        )
        skin_offer = IndustryLpStoreOffer.objects.create(
            offer_id=3003,
            corporation_id=TLIB_CORP_ID,
            type_id=skin.id,
            lp_cost=5_000,
            isk_cost=0,
            quantity=1,
        )
        with _AMAMAKE_PATCH:
            rebuild_lp_store_offer_economics()
        row = IndustryLpStoreOfferEconomics.objects.get(offer=skin_offer)
        self.assertTrue(row.involves_skin)
        hull_row = IndustryLpStoreOfferEconomics.objects.get(offer=self.offer)
        self.assertFalse(hull_row.involves_skin)

    def test_rebuild_replaces_previous_rows(self):
        with _AMAMAKE_PATCH:
            rebuild_lp_store_offer_economics()
            IndustryLpStoreOffer.objects.create(
                offer_id=3002,
                corporation_id=TLIB_CORP_ID,
                type_id=HULL_TYPE_ID,
                lp_cost=10_000,
                isk_cost=0,
                quantity=1,
            )
            count = rebuild_lp_store_offer_economics()
        self.assertEqual(count, 2)
        self.assertEqual(IndustryLpStoreOfferEconomics.objects.count(), 2)
