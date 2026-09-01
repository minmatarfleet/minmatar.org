"""Tests for fitting buy guided workflow helpers."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from eveuniverse.models import EveCategory, EveGroup, EveType

from fittings.models import EveFitting
from market.helpers.fitting_buy_guide import (
    multibuy_blocked,
    resolve_guide_step,
    shopping_landed_complete,
)
from market.helpers.fitting_buy_plan import sync_order_items
from market.models.fitting_buy_order import (
    FittingBuyGuideStep,
    FittingBuyOrder,
    FittingBuyOrderLine,
    FittingBuyOrderStatus,
)


def _type(type_id: int, name: str) -> EveType:
    category, _ = EveCategory.objects.get_or_create(
        id=6, defaults={"name": "Ship", "published": True}
    )
    group, _ = EveGroup.objects.get_or_create(
        id=25,
        defaults={
            "name": "Frigate",
            "published": True,
            "eve_category": category,
        },
    )
    obj, _ = EveType.objects.get_or_create(
        id=type_id,
        defaults={"name": name, "published": True, "eve_group": group},
    )
    if obj.name != name:
        obj.name = name
        obj.save(update_fields=["name"])
    return obj


class FittingBuyGuideTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("guide", password="x")
        self.hull = _type(16210, "Guide Probe")
        self.mod = _type(20490, "Guide DC II")
        self.fitting = EveFitting.objects.create(
            name="[TEST] Guide Probe",
            ship_id=self.hull.id,
            description="test",
            eft_format=f"[{self.hull.name}, Guide]\n{self.mod.name}\n",
        )
        self.order = FittingBuyOrder.objects.create(
            owner=self.user,
            stock_paste=None,
        )
        FittingBuyOrderLine.objects.create(
            order=self.order,
            fitting=self.fitting,
            quantity=2,
        )
        sync_order_items(self.order)

    def test_resolve_starts_on_stock(self):
        self.assertEqual(
            resolve_guide_step(self.order), FittingBuyGuideStep.STOCK
        )

    def test_resolve_purchase_after_stock_confirmed(self):
        self.order.stock_paste = ""
        self.order.save(update_fields=["stock_paste"])
        self.assertEqual(
            resolve_guide_step(self.order), FittingBuyGuideStep.PURCHASE
        )

    def test_multibuy_blocked_while_jita_pending(self):
        blocked, reason = multibuy_blocked(self.order)
        self.assertTrue(blocked)
        self.assertEqual(reason, "jita_pending")

    def test_multibuy_blocked_on_shorts(self):
        item = self.order.items.get(eve_type_id=self.mod.id)
        item.jita_sell_volume = 0
        item.save(update_fields=["jita_sell_volume"])
        self.order.jita_checked_at = self.order.created_at
        self.order.save(update_fields=["jita_checked_at"])

        blocked, reason = multibuy_blocked(self.order)
        self.assertTrue(blocked)
        self.assertEqual(reason, "shorts")

    def test_multibuy_allowed_when_depth_covers_buy(self):
        item = self.order.items.get(eve_type_id=self.mod.id)
        item.jita_sell_volume = 10
        item.save(update_fields=["jita_sell_volume"])
        self.order.jita_checked_at = self.order.created_at
        self.order.save(update_fields=["jita_checked_at"])

        blocked, reason = multibuy_blocked(self.order)
        self.assertFalse(blocked)
        self.assertEqual(reason, "")

    def test_shopping_landed_complete(self):
        self.assertFalse(shopping_landed_complete(self.order))
        item = self.order.items.get(eve_type_id=self.mod.id)
        item.unit_price = Decimal("100")
        item.save(update_fields=["unit_price"])
        self.assertTrue(shopping_landed_complete(self.order))

    def test_resolve_contract_when_pending_and_landed(self):
        self.order.stock_paste = ""
        self.order.status = FittingBuyOrderStatus.PENDING_FITTING
        self.order.save(update_fields=["stock_paste", "status"])
        self.assertEqual(
            resolve_guide_step(self.order), FittingBuyGuideStep.PURCHASE
        )

        item = self.order.items.get(eve_type_id=self.mod.id)
        item.unit_price = Decimal("100")
        item.save(update_fields=["unit_price"])
        self.assertEqual(
            resolve_guide_step(self.order), FittingBuyGuideStep.CONTRACT
        )

    def test_resolve_contract_when_stock_covers_shopping_list(self):
        self.order.stock_paste = f"{self.mod.name}\t2"
        self.order.save(update_fields=["stock_paste"])
        sync_order_items(self.order)
        self.assertTrue(shopping_landed_complete(self.order))
        self.assertEqual(
            resolve_guide_step(self.order), FittingBuyGuideStep.CONTRACT
        )
