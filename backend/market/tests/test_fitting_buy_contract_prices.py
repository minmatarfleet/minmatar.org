"""Tests for fitting buy order contract price recommendations."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from eveonline.models import EveCharacter
from eveuniverse.models import EveCategory, EveGroup, EveType
from ninja.testing import TestClient

from fittings.models import EveFitting
from industry.models import IndustryOrder, IndustryOrderItem
from industry.test_utils import create_industry_order
from market.endpoints.fitting_buy_orders import router
from market.helpers.fitting_buy_contract_prices import build_contract_prices
from market.helpers.fitting_buy_plan import sync_order_items
from market.helpers.fitting_buy_prices import apply_landed_prices
from market.models.fitting_buy_order import (
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


def _auth_headers(user: User) -> dict:
    token = jwt.encode(
        {"user_id": user.id},
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


class FittingBuyContractPricesTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("buyer", password="x")
        self.character = EveCharacter.objects.create(
            character_id=991001,
            character_name="Buyer Char",
            user=self.user,
        )
        self.hull = _type(16200, "Contract Probe")
        self.mod_a = _type(20480, "Contract DC II")
        self.mod_b = _type(5830, "Contract AB II")
        self.mod_sub = _type(20460, "Contract DC I")
        self.fitting = EveFitting.objects.create(
            name="[TEST] Contract Probe",
            ship_id=self.hull.id,
            description="test",
            eft_format=(
                f"[{self.hull.name}, Contract Probe]\n"
                f"{self.mod_a.name}\n"
                f"{self.mod_b.name}\n"
            ),
        )
        self.order = FittingBuyOrder.objects.create(
            owner=self.user,
            include_hull=False,
            status=FittingBuyOrderStatus.PENDING_FITTING,
        )
        FittingBuyOrderLine.objects.create(
            order=self.order,
            fitting=self.fitting,
            quantity=3,
        )
        sync_order_items(self.order)

    def _industry_ask(
        self, eve_type: EveType, unit_price: str, *, fulfilled=False
    ):
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
            fulfilled_at=timezone.now() if fulfilled else None,
        )
        IndustryOrderItem.objects.create(
            order=order,
            eve_type=eve_type,
            quantity=10,
            target_unit_price=Decimal(unit_price),
        )
        return order

    @patch("market.helpers.fitting_buy_contract_prices.get_prices_by_type_id")
    def test_pasted_modules_plus_industry_hull(self, mock_jita):
        mock_jita.return_value = {
            self.hull.id: 20_000_000,
            self.mod_a.id: 1_000_000,
            self.mod_b.id: 2_000_000,
        }
        apply_landed_prices(
            self.order,
            f"{self.mod_a.name}\t1000000\n{self.mod_b.name}\t2000000",
        )
        industry = self._industry_ask(self.hull, "175000000")

        rows = build_contract_prices(self.order)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        # Line qty is 3; costs must still be one hull (not ×3).
        self.assertEqual(row["quantity"], 3)
        # 175M hull + 1M + 2M = 178M per ship
        self.assertEqual(row["landed_per_ship"], "178000000")
        self.assertEqual(row["hull_cost"], "175000000")
        self.assertEqual(row["fitting_cost"], "3000000")
        self.assertTrue(row["landed_complete"])
        self.assertEqual(row["landed_plus_20"], "213600000")
        self.assertEqual(row["jita_sell_per_ship"], "23000000")
        self.assertEqual(row["jita_plus_20"], "27600000")
        self.assertEqual(len(row["industry_sources"]), 1)
        self.assertEqual(row["industry_sources"][0]["order_id"], industry.id)
        self.assertEqual(row["industry_sources"][0]["type_id"], self.hull.id)
        self.assertEqual(row["hull_cost_source"], "industry")
        self.assertEqual(row["hull_cost_industry_order_id"], industry.id)
        self.assertEqual(
            row["hull_cost_industry_short_code"],
            industry.public_short_code or "",
        )
        self.assertFalse(row["hull_cost_from_jita"])
        self.assertNotIn(
            self.hull.id, {item.eve_type_id for item in self.order.items.all()}
        )

    @patch("market.helpers.fitting_buy_contract_prices.get_prices_by_type_id")
    def test_costs_stay_per_ship_when_quantity_changes(self, mock_jita):
        """Fitting / total / markups are per hull; qty only changes the qty column."""
        mock_jita.return_value = {
            self.hull.id: 20_000_000,
            self.mod_a.id: 1_000_000,
            self.mod_b.id: 2_000_000,
        }
        apply_landed_prices(
            self.order,
            f"{self.mod_a.name}\t1000000\n{self.mod_b.name}\t2000000",
        )
        self._industry_ask(self.hull, "175000000")

        line = self.order.lines.get()
        line.quantity = 1
        line.save(update_fields=["quantity"])
        sync_order_items(self.order)
        apply_landed_prices(
            self.order,
            f"{self.mod_a.name}\t1000000\n{self.mod_b.name}\t2000000",
        )
        one = build_contract_prices(self.order)[0]

        line.quantity = 10
        line.save(update_fields=["quantity"])
        sync_order_items(self.order)
        apply_landed_prices(
            self.order,
            f"{self.mod_a.name}\t1000000\n{self.mod_b.name}\t2000000",
        )
        ten = build_contract_prices(self.order)[0]

        self.assertEqual(one["quantity"], 1)
        self.assertEqual(ten["quantity"], 10)
        self.assertEqual(one["hull_cost"], ten["hull_cost"])
        self.assertEqual(one["fitting_cost"], ten["fitting_cost"])
        self.assertEqual(one["landed_per_ship"], ten["landed_per_ship"])
        self.assertEqual(one["landed_plus_20"], ten["landed_plus_20"])
        self.assertEqual(one["jita_plus_20"], ten["jita_plus_20"])
        self.assertEqual(ten["fitting_cost"], "3000000")
        self.assertEqual(ten["landed_per_ship"], "178000000")

    @patch("market.helpers.fitting_buy_contract_prices.get_prices_by_type_id")
    def test_fulfilled_industry_ignored_latest_open_wins(self, mock_jita):
        mock_jita.return_value = {
            self.hull.id: 1,
            self.mod_a.id: 1,
            self.mod_b.id: 1,
        }
        apply_landed_prices(
            self.order,
            f"{self.mod_a.name}\t1\n{self.mod_b.name}\t1",
        )
        self._industry_ask(self.hull, "100000000", fulfilled=True)
        newer = self._industry_ask(self.hull, "200000000")
        older = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
        )
        IndustryOrderItem.objects.create(
            order=older,
            eve_type=self.hull,
            quantity=1,
            target_unit_price=Decimal("150000000"),
        )
        IndustryOrder.objects.filter(pk=older.pk).update(
            created_at=timezone.now() - timedelta(days=2)
        )

        rows = build_contract_prices(self.order)
        self.assertEqual(rows[0]["landed_per_ship"], "200000002")
        self.assertEqual(rows[0]["industry_sources"][0]["order_id"], newer.id)

    @patch("market.helpers.fitting_buy_contract_prices.get_prices_by_type_id")
    def test_pasted_hull_beats_industry(self, mock_jita):
        mock_jita.return_value = {
            self.hull.id: 1,
            self.mod_a.id: 1,
            self.mod_b.id: 1,
        }
        self.order.include_hull = True
        self.order.save(update_fields=["include_hull"])
        sync_order_items(self.order)
        apply_landed_prices(
            self.order,
            (
                f"{self.hull.name}\t50000000\n"
                f"{self.mod_a.name}\t1000000\n"
                f"{self.mod_b.name}\t2000000"
            ),
        )
        self._industry_ask(self.hull, "175000000")

        rows = build_contract_prices(self.order)
        self.assertEqual(rows[0]["landed_per_ship"], "53000000")
        self.assertEqual(rows[0]["industry_sources"], [])
        self.assertEqual(rows[0]["hull_cost_source"], "landed")
        self.assertIsNone(rows[0]["hull_cost_industry_order_id"])
        self.assertEqual(rows[0]["hull_cost_industry_short_code"], "")
        self.assertFalse(rows[0]["hull_cost_from_jita"])

    @patch("market.helpers.fitting_buy_contract_prices.get_prices_by_type_id")
    def test_swapped_fit_changes_landed(self, mock_jita):
        mock_jita.return_value = {
            self.hull.id: 10_000_000,
            self.mod_a.id: 1_000_000,
            self.mod_b.id: 2_000_000,
            self.mod_sub.id: 100_000,
        }
        line = self.order.lines.get()
        line.swaps = [
            {
                "preferred_type_id": self.mod_a.id,
                "substitute_type_id": self.mod_sub.id,
            }
        ]
        line.swap_hull_qty = 1
        line.save(update_fields=["swaps", "swap_hull_qty"])
        sync_order_items(self.order)
        apply_landed_prices(
            self.order,
            (
                f"{self.mod_a.name}\t1000000\n"
                f"{self.mod_b.name}\t2000000\n"
                f"{self.mod_sub.name}\t100000"
            ),
        )
        self._industry_ask(self.hull, "100000000")

        rows = build_contract_prices(self.order)
        self.assertEqual(len(rows), 2)
        by_swapped = {row["is_swapped"]: row for row in rows}
        # Original: 100M + 1M + 2M
        self.assertEqual(by_swapped[False]["landed_per_ship"], "103000000")
        self.assertEqual(by_swapped[False]["quantity"], 2)
        # Swapped: 100M + 0.1M + 2M
        self.assertEqual(by_swapped[True]["landed_per_ship"], "102100000")
        self.assertEqual(by_swapped[True]["quantity"], 1)

    @patch("market.helpers.fitting_buy_contract_prices.get_prices_by_type_id")
    def test_incomplete_landed_still_has_jita_markup(self, mock_jita):
        mock_jita.return_value = {
            self.hull.id: 20_000_000,
            self.mod_a.id: 1_000_000,
            self.mod_b.id: 2_000_000,
        }
        apply_landed_prices(self.order, f"{self.mod_a.name}\t1000000")
        # No industry hull, no mod_b paste — hull falls back to Jita sell.

        rows = build_contract_prices(self.order)
        row = rows[0]
        self.assertFalse(row["landed_complete"])
        self.assertNotIn(self.hull.name, row["missing_type_names"])
        self.assertIn(self.mod_b.name, row["missing_type_names"])
        self.assertTrue(row["hull_cost_from_jita"])
        self.assertEqual(row["hull_cost_source"], "jita")
        self.assertIsNone(row["hull_cost_industry_order_id"])
        self.assertEqual(row["hull_cost"], "20000000")
        # Hull Jita 20M + pasted mod_a 1M
        self.assertEqual(row["landed_per_ship"], "21000000")
        self.assertEqual(row["landed_plus_20"], "25200000")
        self.assertEqual(row["jita_plus_20"], "27600000")

    @patch("market.helpers.fitting_buy_contract_prices.get_prices_by_type_id")
    def test_hull_falls_back_to_jita_sell(self, mock_jita):
        mock_jita.return_value = {
            self.hull.id: 50_000_000,
            self.mod_a.id: 1_000_000,
            self.mod_b.id: 2_000_000,
        }
        apply_landed_prices(
            self.order,
            f"{self.mod_a.name}\t1000000\n{self.mod_b.name}\t2000000",
        )

        rows = build_contract_prices(self.order)
        row = rows[0]
        self.assertTrue(row["landed_complete"])
        self.assertTrue(row["hull_cost_from_jita"])
        self.assertEqual(row["hull_cost_source"], "jita")
        self.assertIsNone(row["hull_cost_industry_order_id"])
        self.assertEqual(row["hull_cost"], "50000000")
        self.assertEqual(row["fitting_cost"], "3000000")
        self.assertEqual(row["landed_per_ship"], "53000000")
        self.assertEqual(row["missing_type_names"], [])
        self.assertEqual(row["industry_sources"], [])

    @patch("market.helpers.fitting_buy_contract_prices.get_prices_by_type_id")
    def test_stock_covered_modules_use_jita_sell(self, mock_jita):
        mock_jita.return_value = {
            self.hull.id: 50_000_000,
            self.mod_a.id: 1_000_000,
            self.mod_b.id: 2_000_000,
        }
        self.order.stock_paste = f"{self.mod_a.name}\t3\n{self.mod_b.name}\t3"
        self.order.save(update_fields=["stock_paste"])
        sync_order_items(self.order)
        self._industry_ask(self.mod_a, "999999999")

        rows = build_contract_prices(self.order)
        row = rows[0]
        self.assertTrue(row["landed_complete"])
        self.assertEqual(row["missing_type_names"], [])
        self.assertEqual(row["industry_sources"], [])
        self.assertTrue(row["hull_cost_from_jita"])
        self.assertEqual(row["hull_cost"], "50000000")
        self.assertEqual(row["fitting_cost"], "3000000")
        self.assertEqual(row["landed_per_ship"], "53000000")

    @patch("market.helpers.fitting_buy_contract_prices.get_prices_by_type_id")
    def test_mixed_stock_and_pasted_buy(self, mock_jita):
        mock_jita.return_value = {
            self.hull.id: 50_000_000,
            self.mod_a.id: 1_000_000,
            self.mod_b.id: 2_000_000,
        }
        self.order.stock_paste = f"{self.mod_a.name}\t3"
        self.order.save(update_fields=["stock_paste"])
        sync_order_items(self.order)
        apply_landed_prices(self.order, f"{self.mod_b.name}\t2500000")

        rows = build_contract_prices(self.order)
        row = rows[0]
        self.assertTrue(row["landed_complete"])
        self.assertEqual(row["missing_type_names"], [])
        self.assertEqual(row["fitting_cost"], "3500000")
        self.assertEqual(row["landed_per_ship"], "53500000")


class FittingBuyContractPricesApiTestCase(TestCase):
    def setUp(self):
        self.client = TestClient(router)
        self.owner = User.objects.create_user("owner", password="x")
        self.hull = _type(16201, "Api Probe")
        self.mod = _type(20481, "Api DC II")
        self.fitting = EveFitting.objects.create(
            name="[TEST] Api Probe",
            ship_id=self.hull.id,
            description="test",
            eft_format=f"[{self.hull.name}, Api]\n{self.mod.name}\n",
        )

    @patch("market.helpers.fitting_buy_contract_prices.get_prices_by_type_id")
    def test_detail_gates_contract_prices_to_contract_step(self, mock_jita):
        mock_jita.return_value = {self.hull.id: 10, self.mod.id: 5}
        order = FittingBuyOrder.objects.create(owner=self.owner)
        FittingBuyOrderLine.objects.create(
            order=order, fitting=self.fitting, quantity=1
        )
        sync_order_items(order)

        response = self.client.get(
            f"/fitting-buy-orders/{order.id}",
            headers=_auth_headers(self.owner),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["guide_step"], "stock")
        self.assertEqual(body["contract_prices"], [])

        order.stock_paste = ""
        order.status = FittingBuyOrderStatus.PENDING_FITTING
        order.save(update_fields=["stock_paste", "status"])
        item = order.items.get(eve_type_id=self.mod.id)
        item.unit_price = Decimal("5")
        item.save(update_fields=["unit_price"])

        response = self.client.get(
            f"/fitting-buy-orders/{order.id}",
            headers=_auth_headers(self.owner),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["guide_step"], "contract")
        self.assertEqual(len(body["contract_prices"]), 1)
        self.assertEqual(
            body["contract_prices"][0]["fitting_id"], self.fitting.id
        )

    @patch("market.helpers.fitting_buy_contract_prices.get_prices_by_type_id")
    def test_detail_advances_to_contract_when_stock_covers_buy(
        self, mock_jita
    ):
        mock_jita.return_value = {self.hull.id: 10, self.mod.id: 5}
        order = FittingBuyOrder.objects.create(
            owner=self.owner,
            stock_paste=f"{self.mod.name}\t1",
        )
        FittingBuyOrderLine.objects.create(
            order=order, fitting=self.fitting, quantity=1
        )
        sync_order_items(order)

        response = self.client.get(
            f"/fitting-buy-orders/{order.id}",
            headers=_auth_headers(self.owner),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["guide_step"], "contract")
        self.assertEqual(len(body["contract_prices"]), 1)
        self.assertTrue(body["contract_prices"][0]["landed_complete"])
        self.assertEqual(body["contract_prices"][0]["fitting_cost"], "5")

    def test_complete_order_pending_fitting_to_completed(self):
        order = FittingBuyOrder.objects.create(
            owner=self.owner,
            status=FittingBuyOrderStatus.PENDING_FITTING,
        )
        FittingBuyOrderLine.objects.create(
            order=order, fitting=self.fitting, quantity=1
        )
        sync_order_items(order)

        response = self.client.patch(
            f"/fitting-buy-orders/{order.id}",
            json={"status": FittingBuyOrderStatus.COMPLETED},
            headers=_auth_headers(self.owner),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "completed")
        order.refresh_from_db()
        self.assertEqual(order.status, FittingBuyOrderStatus.COMPLETED)

        legacy = self.client.patch(
            f"/fitting-buy-orders/{order.id}",
            json={"status": "purchased"},
            headers=_auth_headers(self.owner),
        )
        self.assertEqual(legacy.status_code, 200)
        self.assertEqual(legacy.json()["status"], "completed")

    @patch("market.helpers.fitting_buy_contract_prices.get_prices_by_type_id")
    def test_detail_survives_contract_price_failure(self, mock_jita):
        mock_jita.side_effect = RuntimeError("pricing down")
        order = FittingBuyOrder.objects.create(
            owner=self.owner,
            status=FittingBuyOrderStatus.COMPLETED,
            stock_paste="",
        )
        FittingBuyOrderLine.objects.create(
            order=order, fitting=self.fitting, quantity=1
        )
        sync_order_items(order)

        response = self.client.get(
            f"/fitting-buy-orders/{order.id}",
            headers=_auth_headers(self.owner),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["guide_step"], "contract")
        self.assertEqual(body["contract_prices"], [])
