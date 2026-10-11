"""Shared industry rows stay when the linked user or character is deleted."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import signals
from django.utils import timezone

from app.test import TestCase
from eveonline.models import EveCharacter
from eveuniverse.models import EveCategory, EveGroup, EveType
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLoyaltyPointMarketOrder,
    IndustryLoyaltyPointMarketOrderClaim,
    IndustryOrderItem,
    IndustryOrderItemAssignment,
)
from industry.test_utils import create_industry_order


class SharedIndustryRowDeleteTest(TestCase):
    def setUp(self):
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        super().setUp()

    def test_deleting_issuer_keeps_the_order_and_other_assignment(self):
        issuer = EveCharacter.objects.create(
            character_id=910001,
            character_name="Issuer",
            user=self.user,
        )
        builder_user = User.objects.create(username="builder")
        builder = EveCharacter.objects.create(
            character_id=910002,
            character_name="Builder",
            user=builder_user,
        )
        category = EveCategory.objects.create(
            id=9101, name="Cat", published=True
        )
        group = EveGroup.objects.create(
            id=9101,
            name="Group",
            published=True,
            eve_category=category,
        )
        eve_type = EveType.objects.create(
            id=910201, name="Widget", published=True, eve_group=group
        )
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=3)).date(),
            character=issuer,
        )
        item = IndustryOrderItem.objects.create(
            order=order, eve_type=eve_type, quantity=4
        )
        assignment = IndustryOrderItemAssignment.objects.create(
            order_item=item, character=builder, quantity=4
        )

        issuer.delete()

        order.refresh_from_db()
        self.assertIsNone(order.character_id)
        assignment.refresh_from_db()
        self.assertEqual(assignment.character_id, builder.id)

    def test_deleting_lp_seller_keeps_the_order_and_claim(self):
        seller = User.objects.create(username="lp-seller")
        claimer = User.objects.create(username="lp-claimer")
        currency = IndustryLoyaltyPoint.objects.create(
            name="Test LP", corporation_id=9100182
        )
        order = IndustryLoyaltyPointMarketOrder.objects.create(
            loyalty_point=currency,
            side=IndustryLoyaltyPointMarketOrder.Side.SELL,
            quantity=1000,
            isk_per_lp=800,
            created_by=seller,
        )
        claim = IndustryLoyaltyPointMarketOrderClaim.objects.create(
            order=order, amount=400, claimed_by=claimer
        )

        seller.delete()

        order.refresh_from_db()
        claim.refresh_from_db()
        self.assertIsNone(order.created_by_id)
        self.assertEqual(claim.claimed_by_id, claimer.id)
        self.assertEqual(claim.amount, 400)

    def test_deleting_lp_claimer_keeps_the_fill(self):
        seller = User.objects.create(username="lp-seller-2")
        claimer = User.objects.create(username="lp-claimer-2")
        currency = IndustryLoyaltyPoint.objects.create(
            name="Test LP 2", corporation_id=9100183
        )
        order = IndustryLoyaltyPointMarketOrder.objects.create(
            loyalty_point=currency,
            side=IndustryLoyaltyPointMarketOrder.Side.SELL,
            quantity=1000,
            isk_per_lp=800,
            created_by=seller,
            claimed_by=claimer,
        )
        claim = IndustryLoyaltyPointMarketOrderClaim.objects.create(
            order=order, amount=250, claimed_by=claimer
        )

        claimer.delete()

        order.refresh_from_db()
        claim.refresh_from_db()
        self.assertEqual(order.created_by_id, seller.id)
        self.assertIsNone(order.claimed_by_id)
        self.assertIsNone(claim.claimed_by_id)
        self.assertEqual(claim.amount, 250)
