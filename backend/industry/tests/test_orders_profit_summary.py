"""Tests for GET /api/industry/orders/profit-summary."""

from datetime import timedelta
from unittest.mock import patch

from django.test import Client
from django.utils import timezone
from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter, EveLocation
from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase as AppTestCase
from industry.helpers.product_unit_cost import ProductUnitCost
from industry.models import IndustryOrderItem
from industry.test_utils import create_industry_order


class OrdersProfitSummaryEndpointTestCase(AppTestCase):
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
        self.client = Client()
        self.character = EveCharacter.objects.get_or_create(
            character_id=999101,
            defaults={"character_name": "Profit Char", "user": self.user},
        )[0]
        set_primary_character(self.user, self.character)
        self.eve_type = EveType.objects.create(
            id=999301,
            name="Test Hull",
            published=True,
            eve_group=self.eve_group,
        )
        self.location = EveLocation.objects.create(
            location_id=1999101,
            location_name="Profit Station",
            solar_system_id=300001,
            solar_system_name="Test System",
            short_name="PRF",
        )

    def _unit_cost(self, type_id: int, name: str) -> ProductUnitCost:
        return ProductUnitCost(
            type_id=type_id,
            name=name,
            kind="T1",
            cost_per=1_000_000,
            jita_sell=1_500_000,
            profit_per=500_000,
            isk_per_lp=None,
            note=None,
        )

    @patch("industry.helpers.orders_profit_summary.plan_product_unit_cost")
    @patch(
        "industry.helpers.orders_profit_summary.jita_sell_prices_by_type_id"
    )
    def test_profit_summary_aggregates_included_orders(
        self, mock_prices, mock_plan
    ):
        mock_prices.return_value = {self.eve_type.id: 1_500_000}
        mock_plan.side_effect = lambda tid, **kw: self._unit_cost(
            tid, self.eve_type.name
        )

        needed = (timezone.now() + timedelta(days=14)).date()
        order_a = create_industry_order(
            needed_by=needed,
            character=self.character,
            location=self.location,
        )
        IndustryOrderItem.objects.create(
            order=order_a,
            eve_type=self.eve_type,
            quantity=10,
            self_assign_maximum=100,
        )
        order_b = create_industry_order(
            needed_by=needed,
            character=self.character,
            location=self.location,
        )
        IndustryOrderItem.objects.create(
            order=order_b, eve_type=self.eve_type, quantity=5
        )

        response = self.client.get(
            "/api/industry/orders/profit-summary",
            {
                "needed_by_from": needed.isoformat(),
                "needed_by_to": needed.isoformat(),
                "open_only": "true",
                "order_ids": str(order_a.pk),
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["orders"]), 2)
        included = {o["id"]: o["included"] for o in data["orders"]}
        self.assertTrue(included[order_a.pk])
        self.assertFalse(included[order_b.pk])
        self.assertEqual(len(data["rows"]), 1)
        row = data["rows"][0]
        self.assertEqual(row["type_id"], self.eve_type.id)
        self.assertEqual(row["qty"], 10)
        self.assertEqual(row["order_profit"], 5_000_000)
        self.assertEqual(data["totals"]["total_profit"], 5_000_000)
        # Ask missing → Jita 1.5M × 10
        self.assertEqual(data["totals"]["total_order_amount"], 15_000_000)
        assumptions_text = " ".join(data["assumptions"]).lower()
        self.assertIn("order ask", assumptions_text)
        self.assertIn("maximum claim", assumptions_text)
        mock_plan.assert_called()
        _, plan_kwargs = mock_plan.call_args
        self.assertEqual(plan_kwargs.get("quantity"), 100)

    @patch("industry.helpers.orders_profit_summary.plan_product_unit_cost")
    @patch(
        "industry.helpers.orders_profit_summary.jita_sell_prices_by_type_id"
    )
    def test_profit_summary_excludes_fulfilled_when_open_only(
        self, mock_prices, mock_plan
    ):
        mock_prices.return_value = {}
        mock_plan.side_effect = lambda tid, **kw: self._unit_cost(
            tid, self.eve_type.name
        )

        needed = (timezone.now() + timedelta(days=7)).date()
        open_order = create_industry_order(
            needed_by=needed,
            character=self.character,
            location=self.location,
        )
        IndustryOrderItem.objects.create(
            order=open_order, eve_type=self.eve_type, quantity=2
        )
        done = create_industry_order(
            needed_by=needed,
            character=self.character,
            location=self.location,
        )
        done.fulfilled_at = timezone.now()
        done.save(update_fields=["fulfilled_at"])
        IndustryOrderItem.objects.create(
            order=done, eve_type=self.eve_type, quantity=99
        )

        response = self.client.get(
            "/api/industry/orders/profit-summary",
            {"open_only": "true"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        ids = {o["id"] for o in data["orders"]}
        self.assertIn(open_order.pk, ids)
        self.assertNotIn(done.pk, ids)

    def test_profit_summary_rejects_unknown_facility(self):
        response = self.client.get(
            "/api/industry/orders/profit-summary",
            {"facility_key": "not-a-facility"},
        )
        self.assertEqual(response.status_code, 400)
