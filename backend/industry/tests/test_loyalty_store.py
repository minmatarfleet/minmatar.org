"""Tests for industry.helpers.loyalty_store."""

from unittest.mock import patch

from django.test import TestCase

from industry.helpers.loyalty_store import (
    ensure_loyalty_store_offers_for_product,
    get_offer_for_blueprint_type,
    is_pure_lp_isk_offer,
    navy_bpc_cost_for_plan,
    resolve_isk_per_lp,
    sync_loyalty_store_offers,
)
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLpStoreOffer,
    IndustryProduct,
    Strategy,
)
from eveuniverse.models import EveCategory, EveGroup, EveType

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
            count = sync_loyalty_store_offers(
                corporation_ids=[TLIB_CORP_ID], offers=TYFI_OFFERS
            )
        self.assertEqual(count, 1)
        row = IndustryLpStoreOffer.objects.get()
        self.assertEqual(row.offer_id, 16343)
        self.assertEqual(row.lp_cost, 100_000)
        self.assertEqual(row.isk_cost, 20_000_000)
        self.assertEqual(row.quantity, 1)

    def test_navy_bpc_cost_at_800_isk_per_lp(self):
        sync_loyalty_store_offers(
            corporation_ids=[TLIB_CORP_ID], offers=TYFI_OFFERS
        )
        cost = navy_bpc_cost_for_plan(TYFI_BP_TYPE_ID, 40, 800.0)
        self.assertIsNotNone(cost)
        assert cost is not None
        self.assertEqual(cost.packs, 40)
        self.assertEqual(cost.total_isk, 40 * 100_000_000)
        self.assertEqual(cost.offer_id, 16343)

    def test_pack_quantity_ceil(self):
        sync_loyalty_store_offers(
            corporation_ids=[TLIB_CORP_ID],
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
            ],
        )
        cost = navy_bpc_cost_for_plan(999, 40, 800.0)
        self.assertIsNotNone(cost)
        assert cost is not None
        self.assertEqual(cost.packs, 4)
        self.assertEqual(cost.total_isk, 4 * (10_000 * 800 + 1_000_000))

    def test_get_offer_skips_esi_when_cached(self):
        sync_loyalty_store_offers(
            corporation_ids=[TLIB_CORP_ID], offers=TYFI_OFFERS
        )
        with patch(
            "industry.helpers.loyalty_store.sync_loyalty_store_offers"
        ) as mock_sync:
            offer = get_offer_for_blueprint_type(TYFI_BP_TYPE_ID)
            mock_sync.assert_not_called()
        self.assertIsNotNone(offer)
        assert offer is not None
        self.assertEqual(offer.offer_id, 16343)

    def test_resolve_isk_per_lp_uses_loyalty_point_default(self):
        IndustryLoyaltyPoint.objects.update_or_create(
            corporation_id=TLIB_CORP_ID,
            defaults={
                "name": "TLIB",
                "default_isk_per_lp": 750,
                "is_active": True,
            },
        )
        self.assertEqual(
            resolve_isk_per_lp(requested=None, corporation_id=TLIB_CORP_ID),
            750.0,
        )
        self.assertEqual(
            resolve_isk_per_lp(requested=900, corporation_id=TLIB_CORP_ID),
            900.0,
        )

    @patch("industry.tasks.ensure_loyalty_store_offers_for_product_task.delay")
    @patch("industry.helpers.loyalty_store.sync_loyalty_store_offers")
    def test_ensure_for_product_syncs_when_offer_missing(
        self, sync_mock, delay_mock
    ):
        sync_mock.return_value = 3
        category = EveCategory.objects.create(
            id=6, name="Ship", published=True
        )
        group = EveGroup.objects.create(
            id=9001, name="Battleship", published=True, eve_category=category
        )
        hull = EveType.objects.create(
            id=9002,
            name="Ensure Typhoon Fleet Issue",
            published=True,
            eve_group=group,
        )
        bp = EveType.objects.create(
            id=9003,
            name="Ensure Typhoon Fleet Issue Blueprint",
            published=True,
            eve_group=group,
        )
        from eveuniverse.models import (  # pylint: disable=import-outside-toplevel
            EveIndustryActivityDuration,
            EveIndustryActivityMaterial,
            EveIndustryActivityProduct,
        )

        EveIndustryActivityProduct.objects.create(
            eve_type=bp, activity_id=1, product_eve_type=hull, quantity=1
        )
        EveIndustryActivityDuration.objects.create(
            eve_type=bp, activity_id=1, time=100
        )
        EveIndustryActivityMaterial.objects.create(
            eve_type=bp,
            activity_id=1,
            material_eve_type=hull,
            quantity=1,
        )
        product = IndustryProduct.objects.create(
            eve_type=hull, strategy=Strategy.IMPORTED
        )
        delay_mock.assert_called_once_with(product.pk)
        count = ensure_loyalty_store_offers_for_product(product.pk)
        self.assertEqual(count, 3)
        sync_mock.assert_called_once()
