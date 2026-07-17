"""Tests for industry.helpers.loyalty_store."""

from unittest.mock import patch

from django.test import TestCase

from industry.helpers.loyalty_store import (
    get_offer_for_blueprint_type,
    is_pure_lp_isk_offer,
    navy_bpc_cost_for_plan,
    sync_loyalty_store_offers,
)
from industry.models import IndustryLpStoreOffer

# Typhoon Fleet Issue Blueprint
TYFI_BP_TYPE_ID = 32312
TLIB_CORP_ID = 1000182

TYFI_OFFERS = [
    {
        "offer_id": 16343,
        "corporation_id": TLIB_CORP_ID,
        "type_id": TYFI_BP_TYPE_ID,
        "lp_cost": 100_000,
        "isk_cost": 20_000_000,
        "quantity": 1,
        "required_items": [],
    },
    {
        "offer_id": 19404,
        "corporation_id": TLIB_CORP_ID,
        "type_id": TYFI_BP_TYPE_ID,
        "lp_cost": 100_000,
        "isk_cost": 0,
        "quantity": 1,
        "required_items": [{"quantity": 2, "type_id": 17814}],
    },
    {
        "offer_id": 16342,
        "corporation_id": TLIB_CORP_ID,
        "type_id": TYFI_BP_TYPE_ID,
        "lp_cost": 100_000,
        "isk_cost": 0,
        "quantity": 1,
        "required_items": [{"quantity": 1, "type_id": 17305}],
    },
    {
        "offer_id": 19599,
        "corporation_id": TLIB_CORP_ID,
        "type_id": TYFI_BP_TYPE_ID,
        "lp_cost": 200_000,
        "isk_cost": 200_000_000,
        "quantity": 10,
        "required_items": [{"quantity": 8, "type_id": 93609}],
    },
]


class LoyaltyStoreHelperTestCase(TestCase):
    def test_is_pure_lp_isk_offer(self):
        self.assertTrue(is_pure_lp_isk_offer(TYFI_OFFERS[0]))
        self.assertFalse(is_pure_lp_isk_offer(TYFI_OFFERS[1]))
        self.assertFalse(is_pure_lp_isk_offer(TYFI_OFFERS[2]))
        self.assertFalse(is_pure_lp_isk_offer(TYFI_OFFERS[3]))

    def test_sync_keeps_only_pure_lp_isk(self):
        with patch(
            "industry.helpers.loyalty_store.fetch_loyalty_offers_from_esi"
        ) as mock_fetch:
            mock_fetch.side_effect = AssertionError("ESI should not be called")
            count = sync_loyalty_store_offers(offers=TYFI_OFFERS)
        self.assertEqual(count, 1)
        row = IndustryLpStoreOffer.objects.get()
        self.assertEqual(row.offer_id, 16343)
        self.assertEqual(row.lp_cost, 100_000)
        self.assertEqual(row.isk_cost, 20_000_000)
        self.assertEqual(row.quantity, 1)

    def test_navy_bpc_cost_at_800_isk_per_lp(self):
        sync_loyalty_store_offers(offers=TYFI_OFFERS)
        cost = navy_bpc_cost_for_plan(TYFI_BP_TYPE_ID, 40, 800.0)
        self.assertIsNotNone(cost)
        assert cost is not None
        self.assertEqual(cost.packs, 40)
        self.assertEqual(cost.total_isk, 40 * 100_000_000)
        self.assertEqual(cost.offer_id, 16343)

    def test_pack_quantity_ceil(self):
        sync_loyalty_store_offers(
            offers=[
                {
                    "offer_id": 1,
                    "corporation_id": TLIB_CORP_ID,
                    "type_id": 999,
                    "lp_cost": 10_000,
                    "isk_cost": 1_000_000,
                    "quantity": 10,
                    "required_items": [],
                }
            ]
        )
        cost = navy_bpc_cost_for_plan(999, 40, 800.0)
        self.assertIsNotNone(cost)
        assert cost is not None
        self.assertEqual(cost.packs, 4)
        self.assertEqual(cost.total_isk, 4 * (10_000 * 800 + 1_000_000))

    def test_get_offer_skips_esi_when_cached(self):
        sync_loyalty_store_offers(offers=TYFI_OFFERS)
        with patch(
            "industry.helpers.loyalty_store.sync_loyalty_store_offers"
        ) as mock_sync:
            offer = get_offer_for_blueprint_type(TYFI_BP_TYPE_ID)
            mock_sync.assert_not_called()
        self.assertIsNotNone(offer)
        assert offer is not None
        self.assertEqual(offer.offer_id, 16343)
