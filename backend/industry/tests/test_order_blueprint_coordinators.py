"""Tests for order LP stockpiles and blueprint coordinators."""

import json
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone
from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter, EveCorporation
from eveuniverse.models import (
    EveCategory,
    EveGroup,
    EveIndustryActivityProduct,
    EveType,
)

from app.test import TestCase as AppTestCase
from industry.helpers.lp_ledger import post_ledger_entry
from industry.helpers.order_lp_stockpiles import (
    resolve_order_lp_stockpiles,
    validate_coordinator_eve_type_ids,
)
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLoyaltyPointAccount,
    IndustryLoyaltyPointContact,
    IndustryLpStoreOffer,
    IndustryOrderBlueprintCoordinator,
    IndustryOrderItem,
)
from industry.test_utils import create_industry_order

TLIB_CORP_ID = 1000182


class OrderLpStockpileHelperTestCase(AppTestCase):
    """resolve_order_lp_stockpiles matches navy BPC corps to stockpile accounts."""

    def setUp(self):
        super().setUp()
        self.ship_cat, _ = EveCategory.objects.get_or_create(
            id=6, defaults={"name": "Ship", "published": True}
        )
        self.bs_group, _ = EveGroup.objects.get_or_create(
            id=27,
            defaults={
                "name": "Battleship",
                "published": True,
                "eve_category": self.ship_cat,
            },
        )
        self.bp_group, _ = EveGroup.objects.get_or_create(
            id=105,
            defaults={
                "name": "Blueprint",
                "published": True,
                "eve_category": self.ship_cat,
            },
        )
        self.navy = EveType.objects.create(
            id=910001,
            name="Tempest Fleet Issue",
            published=True,
            eve_group=self.bs_group,
        )
        self.navy_bp = EveType.objects.create(
            id=910002,
            name="Tempest Fleet Issue Blueprint",
            published=True,
            eve_group=self.bp_group,
        )
        EveIndustryActivityProduct.objects.create(
            eve_type=self.navy_bp,
            activity_id=1,
            product_eve_type=self.navy,
            quantity=1,
        )
        self.mineral_cat, _ = EveCategory.objects.get_or_create(
            id=4, defaults={"name": "Material", "published": True}
        )
        self.mineral_group, _ = EveGroup.objects.get_or_create(
            id=18,
            defaults={
                "name": "Mineral",
                "published": True,
                "eve_category": self.mineral_cat,
            },
        )
        self.mineral = EveType.objects.create(
            id=910003,
            name="Tritanium",
            published=True,
            eve_group=self.mineral_group,
        )
        self.currency, _ = IndustryLoyaltyPoint.objects.update_or_create(
            corporation_id=TLIB_CORP_ID,
            defaults={
                "name": "Tribal Liberation Force",
                "default_isk_per_lp": 800,
                "is_active": True,
            },
        )
        IndustryLpStoreOffer.objects.update_or_create(
            offer_id=910100,
            defaults={
                "corporation_id": TLIB_CORP_ID,
                "type_id": self.navy_bp.id,
                "lp_cost": 10000,
                "isk_cost": 1_000_000,
                "quantity": 1,
            },
        )
        self.stockpile = IndustryLoyaltyPointAccount.objects.create(
            loyalty_point=self.currency,
            name="FL33T TLIB pot",
            role=IndustryLoyaltyPointAccount.Role.STOCKPILE,
        )
        self.seller = IndustryLoyaltyPointAccount.objects.create(
            loyalty_point=self.currency,
            name="External seller",
            role=IndustryLoyaltyPointAccount.Role.SELLER,
        )
        IndustryLoyaltyPointContact.objects.create(
            account=self.stockpile,
            character_name="LP Contact",
            discord_username="lpcontact",
            is_active=True,
        )
        post_ledger_entry(self.stockpile, 50_000, 825)
        self.character = EveCharacter.objects.get_or_create(
            character_id=910100,
            defaults={"character_name": "Order Owner", "user": self.user},
        )[0]

    @patch("industry.helpers.loyalty_store.sync_loyalty_store_offers")
    def test_navy_order_returns_active_stockpile(self, mock_sync):
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=self.navy, quantity=2
        )
        rows = resolve_order_lp_stockpiles(order)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].account_id, self.stockpile.pk)
        self.assertEqual(rows[0].balance, 50_000)
        self.assertEqual(rows[0].corporation_id, TLIB_CORP_ID)
        self.assertEqual(len(rows[0].contacts), 1)
        self.assertEqual(rows[0].contacts[0].character_name, "LP Contact")

    @patch("industry.helpers.loyalty_store.sync_loyalty_store_offers")
    def test_stockpile_exposes_character_and_corp_holder_ids(self, mock_sync):
        holder = EveCharacter.objects.get_or_create(
            character_id=910200,
            defaults={"character_name": "BearThatCares", "user": self.user},
        )[0]
        self.stockpile.eve_character = holder
        self.stockpile.save(update_fields=["eve_character"])

        EveCorporation.objects.create(
            corporation_id=98735318,
            name="Minmatar Fleet Holdings",
        )
        # Explicit corporation_name field.
        corp_stockpile = IndustryLoyaltyPointAccount.objects.create(
            loyalty_point=self.currency,
            name="MFH pot",
            role=IndustryLoyaltyPointAccount.Role.STOCKPILE,
            corporation_name="Minmatar Fleet Holdings",
        )
        # Production-style: corp wallet named after the corp, corporation_name blank.
        corp_stockpile_by_name = IndustryLoyaltyPointAccount.objects.create(
            loyalty_point=self.currency,
            name="Minmatar Fleet Holdings",
            role=IndustryLoyaltyPointAccount.Role.STOCKPILE,
            corporation_name="",
        )
        post_ledger_entry(corp_stockpile, 10_000, 825)
        post_ledger_entry(corp_stockpile_by_name, 5_000, 825)

        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=self.navy, quantity=1
        )
        rows = {r.account_id: r for r in resolve_order_lp_stockpiles(order)}

        char_row = rows[self.stockpile.pk]
        self.assertEqual(char_row.character_id, 910200)
        self.assertIsNone(char_row.account_corporation_id)

        corp_row = rows[corp_stockpile.pk]
        self.assertIsNone(corp_row.character_id)
        self.assertEqual(corp_row.account_corporation_id, 98735318)

        name_only_row = rows[corp_stockpile_by_name.pk]
        self.assertIsNone(name_only_row.character_id)
        self.assertEqual(name_only_row.account_corporation_id, 98735318)

    @patch("industry.helpers.loyalty_store.sync_loyalty_store_offers")
    def test_non_navy_order_returns_empty(self, mock_sync):
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=self.mineral, quantity=100
        )
        self.assertEqual(resolve_order_lp_stockpiles(order), [])

    @patch("industry.helpers.loyalty_store.sync_loyalty_store_offers")
    def test_inactive_and_seller_accounts_excluded(self, mock_sync):
        IndustryLoyaltyPointAccount.objects.create(
            loyalty_point=self.currency,
            name="Inactive pot",
            role=IndustryLoyaltyPointAccount.Role.STOCKPILE,
            is_active=False,
        )
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=self.navy, quantity=1
        )
        rows = resolve_order_lp_stockpiles(order)
        account_ids = {r.account_id for r in rows}
        self.assertEqual(account_ids, {self.stockpile.pk})
        self.assertNotIn(self.seller.pk, account_ids)


class BlueprintCoordinatorApiTestCase(AppTestCase):
    """POST/PATCH/DELETE blueprint coordinators and order detail payload."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.eve_category, _ = EveCategory.objects.get_or_create(
            id=1, defaults={"name": "Test Category", "published": True}
        )
        cls.eve_group, _ = EveGroup.objects.get_or_create(
            id=1,
            defaults={
                "name": "Test Group",
                "published": True,
                "eve_category": cls.eve_category,
            },
        )

    def setUp(self):
        super().setUp()
        self.character = EveCharacter.objects.get_or_create(
            character_id=911001,
            defaults={"character_name": "Coord Pilot", "user": self.user},
        )[0]
        set_primary_character(self.user, self.character)
        self.eve_type = EveType.objects.create(
            id=911201,
            name="Coord Ship A",
            published=True,
            eve_group=self.eve_group,
        )
        self.eve_type_b = EveType.objects.create(
            id=911202,
            name="Coord Ship B",
            published=True,
            eve_group=self.eve_group,
        )
        self.order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
        )
        IndustryOrderItem.objects.create(
            order=self.order, eve_type=self.eve_type, quantity=5
        )
        IndustryOrderItem.objects.create(
            order=self.order, eve_type=self.eve_type_b, quantity=3
        )

    def test_validate_rejects_types_not_on_order(self):
        err = validate_coordinator_eve_type_ids(self.order, [999999])
        self.assertIsNotNone(err)
        self.assertIn("999999", err)

    def test_post_creates_coordinator(self):
        response = self.client.post(
            f"/api/industry/orders/{self.order.pk}/blueprint-coordinators",
            data=json.dumps(
                {
                    "character_id": self.character.character_id,
                    "eve_type_ids": [self.eve_type.id],
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["character_id"], self.character.character_id)
        self.assertEqual(len(data["eve_types"]), 1)
        self.assertEqual(data["eve_types"][0]["eve_type_id"], self.eve_type.id)
        self.assertEqual(
            IndustryOrderBlueprintCoordinator.objects.filter(
                order=self.order
            ).count(),
            1,
        )

    def test_post_upserts_same_character(self):
        url = f"/api/industry/orders/{self.order.pk}/blueprint-coordinators"
        self.client.post(
            url,
            data=json.dumps(
                {
                    "character_id": self.character.character_id,
                    "eve_type_ids": [self.eve_type.id],
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        response = self.client.post(
            url,
            data=json.dumps(
                {
                    "character_id": self.character.character_id,
                    "eve_type_ids": [self.eve_type.id, self.eve_type_b.id],
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.json()["eve_types"]), 2)
        self.assertEqual(
            IndustryOrderBlueprintCoordinator.objects.filter(
                order=self.order
            ).count(),
            1,
        )

    def test_multiple_coordinators_allowed(self):
        other_user = self.user.__class__.objects.create(username="other_coord")
        other_char = EveCharacter.objects.create(
            character_id=911002,
            character_name="Other Coord",
            user=other_user,
        )
        IndustryOrderBlueprintCoordinator.objects.create(
            order=self.order, character=self.character
        ).eve_types.set([self.eve_type])
        IndustryOrderBlueprintCoordinator.objects.create(
            order=self.order, character=other_char
        ).eve_types.set([self.eve_type_b])
        self.assertEqual(
            IndustryOrderBlueprintCoordinator.objects.filter(
                order=self.order
            ).count(),
            2,
        )

    def test_post_rejects_foreign_character(self):
        other_user = self.user.__class__.objects.create(username="foreign")
        foreign = EveCharacter.objects.create(
            character_id=911003,
            character_name="Foreign",
            user=other_user,
        )
        response = self.client.post(
            f"/api/industry/orders/{self.order.pk}/blueprint-coordinators",
            data=json.dumps(
                {
                    "character_id": foreign.character_id,
                    "eve_type_ids": [self.eve_type.id],
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_post_rejects_types_not_on_order(self):
        response = self.client.post(
            f"/api/industry/orders/{self.order.pk}/blueprint-coordinators",
            data=json.dumps(
                {
                    "character_id": self.character.character_id,
                    "eve_type_ids": [self.eve_type.id, 999888],
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)

    def test_patch_and_delete(self):
        coordinator = IndustryOrderBlueprintCoordinator.objects.create(
            order=self.order, character=self.character
        )
        coordinator.eve_types.set([self.eve_type])

        patch_response = self.client.patch(
            f"/api/industry/orders/{self.order.pk}/blueprint-coordinators/"
            f"{coordinator.pk}",
            data=json.dumps({"eve_type_ids": [self.eve_type_b.id]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(
            patch_response.status_code, 200, patch_response.content
        )
        self.assertEqual(
            patch_response.json()["eve_types"][0]["eve_type_id"],
            self.eve_type_b.id,
        )

        delete = self.client.delete(
            f"/api/industry/orders/{self.order.pk}/blueprint-coordinators/"
            f"{coordinator.pk}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(delete.status_code, 204)
        self.assertFalse(
            IndustryOrderBlueprintCoordinator.objects.filter(
                pk=coordinator.pk
            ).exists()
        )

    @patch("industry.helpers.loyalty_store.sync_loyalty_store_offers")
    def test_order_detail_includes_coordinators_and_stockpiles(
        self, mock_sync
    ):
        coordinator = IndustryOrderBlueprintCoordinator.objects.create(
            order=self.order, character=self.character
        )
        coordinator.eve_types.set([self.eve_type])
        response = self.client.get(f"/api/industry/orders/{self.order.pk}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("lp_stockpiles", data)
        self.assertIn("blueprint_coordinators", data)
        self.assertEqual(len(data["blueprint_coordinators"]), 1)
        self.assertEqual(
            data["blueprint_coordinators"][0]["character_id"],
            self.character.character_id,
        )
        self.assertEqual(
            data["blueprint_coordinators"][0]["eve_types"][0]["eve_type_id"],
            self.eve_type.id,
        )
