"""Tests for order profit breakdown snapshots and GET profit-summary compose."""

import json
from datetime import timedelta
from unittest.mock import patch

import jwt
from django.conf import settings
from django.test import Client
from django.utils import timezone
from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter, EveLocation
from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase as AppTestCase
from groups.helpers.feature_access import clear_feature_cache
from groups.management.commands.sync_pilot_features import (
    Command as SyncPilotFeaturesCommand,
)
from groups.models import PilotFeature
from industry.helpers.order_profit_breakdown import (
    ProfitBreakdownRefreshNotAllowed,
    compose_orders_profit_summary_from_snapshots,
    ensure_order_profit_breakdown,
    refresh_order_profit_breakdown,
)
from industry.helpers.product_unit_cost import ProductUnitCost
from industry.models import IndustryOrder, IndustryOrderItem
from industry.test_utils import create_industry_order
from tribes.models import Tribe, TribeGroup


class OrderProfitBreakdownTestCase(AppTestCase):
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
            character_id=999201,
            defaults={"character_name": "Snapshot Char", "user": self.user},
        )[0]
        set_primary_character(self.user, self.character)
        self.eve_type = EveType.objects.create(
            id=999401,
            name="Snapshot Hull",
            published=True,
            eve_group=self.eve_group,
        )
        self.location = EveLocation.objects.create(
            location_id=1999201,
            location_name="Snapshot Station",
            solar_system_id=300001,
            solar_system_name="Test System",
            short_name="SNP",
        )
        self.token = jwt.encode(
            {"user_id": self.user.id},
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        tribe = Tribe.objects.create(
            name="Industry", slug="industry-snap", chief=self.user
        )
        tribe_group = TribeGroup.objects.create(
            tribe=tribe, name="Mining", code="industry.mining.snap"
        )
        SyncPilotFeaturesCommand().handle()
        feature = PilotFeature.objects.get(code="industry.order.submit")
        feature.tribe_groups.set([tribe_group])
        clear_feature_cache()

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
    def test_ensure_stores_breakdown(self, mock_prices, mock_plan):
        mock_prices.return_value = {self.eve_type.id: 1_500_000}
        mock_plan.side_effect = lambda tid, **kw: self._unit_cost(
            tid, self.eve_type.name
        )
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
            location=self.location,
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=self.eve_type, quantity=10
        )
        payload = ensure_order_profit_breakdown(order)
        order.refresh_from_db()
        self.assertIsNotNone(order.profit_breakdown)
        self.assertIsNotNone(order.profit_breakdown_computed_at)
        self.assertEqual(payload["rows"][0]["qty"], 10)
        self.assertEqual(payload["totals"]["total_profit"], 5_000_000)

    @patch("industry.helpers.orders_profit_summary.plan_product_unit_cost")
    @patch(
        "industry.helpers.orders_profit_summary.jita_sell_prices_by_type_id"
    )
    def test_compose_sums_snapshots(self, mock_prices, mock_plan):
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
            order=order_a, eve_type=self.eve_type, quantity=10
        )
        order_b = create_industry_order(
            needed_by=needed,
            character=self.character,
            location=self.location,
        )
        IndustryOrderItem.objects.create(
            order=order_b, eve_type=self.eve_type, quantity=5
        )
        ensure_order_profit_breakdown(order_a)
        ensure_order_profit_breakdown(order_b)

        summary = compose_orders_profit_summary_from_snapshots(
            needed_by_from=needed,
            needed_by_to=needed,
            open_only=True,
            order_ids=[order_a.pk, order_b.pk],
        )
        self.assertEqual(len(summary.rows), 1)
        self.assertEqual(summary.rows[0].qty, 15)
        self.assertEqual(summary.rows[0].order_profit, 7_500_000)
        self.assertEqual(summary.totals.total_profit, 7_500_000)

    @patch("industry.helpers.orders_profit_summary.plan_product_unit_cost")
    @patch(
        "industry.helpers.orders_profit_summary.jita_sell_prices_by_type_id"
    )
    def test_refresh_open_order(self, mock_prices, mock_plan):
        mock_prices.return_value = {self.eve_type.id: 1_500_000}
        mock_plan.side_effect = lambda tid, **kw: self._unit_cost(
            tid, self.eve_type.name
        )
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
            location=self.location,
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=self.eve_type, quantity=2
        )
        ensure_order_profit_breakdown(order)
        first_at = order.profit_breakdown_computed_at
        payload = refresh_order_profit_breakdown(order)
        order.refresh_from_db()
        self.assertIsNotNone(order.profit_breakdown_computed_at)
        self.assertGreaterEqual(order.profit_breakdown_computed_at, first_at)
        self.assertEqual(payload["rows"][0]["qty"], 2)

    @patch("industry.helpers.orders_profit_summary.plan_product_unit_cost")
    @patch(
        "industry.helpers.orders_profit_summary.jita_sell_prices_by_type_id"
    )
    def test_refresh_fulfilled_without_snapshot(self, mock_prices, mock_plan):
        mock_prices.return_value = {self.eve_type.id: 1_500_000}
        mock_plan.side_effect = lambda tid, **kw: self._unit_cost(
            tid, self.eve_type.name
        )
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
            location=self.location,
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=self.eve_type, quantity=2
        )
        order.fulfilled_at = timezone.now()
        order.save(update_fields=["fulfilled_at"])
        self.assertIsNone(order.profit_breakdown)
        payload = refresh_order_profit_breakdown(order)
        order.refresh_from_db()
        self.assertIsNotNone(order.profit_breakdown)
        self.assertEqual(payload["rows"][0]["qty"], 2)

    @patch("industry.helpers.orders_profit_summary.plan_product_unit_cost")
    @patch(
        "industry.helpers.orders_profit_summary.jita_sell_prices_by_type_id"
    )
    def test_refresh_fulfilled_with_snapshot_rejected(
        self, mock_prices, mock_plan
    ):
        mock_prices.return_value = {self.eve_type.id: 1_500_000}
        mock_plan.side_effect = lambda tid, **kw: self._unit_cost(
            tid, self.eve_type.name
        )
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
            location=self.location,
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=self.eve_type, quantity=2
        )
        ensure_order_profit_breakdown(order)
        order.fulfilled_at = timezone.now()
        order.save(update_fields=["fulfilled_at"])
        with self.assertRaises(ProfitBreakdownRefreshNotAllowed):
            refresh_order_profit_breakdown(order)

    @patch("industry.helpers.orders_profit_summary.plan_product_unit_cost")
    @patch(
        "industry.helpers.orders_profit_summary.jita_sell_prices_by_type_id"
    )
    def test_post_create_stores_breakdown(self, mock_prices, mock_plan):
        mock_prices.return_value = {self.eve_type.id: 1_500_000}
        mock_plan.side_effect = lambda tid, **kw: self._unit_cost(
            tid, self.eve_type.name
        )
        needed = (timezone.now() + timedelta(days=14)).date().isoformat()
        body = {
            "needed_by": needed,
            "character_id": self.character.character_id,
            "items": [{"eve_type_id": self.eve_type.id, "quantity": 3}],
        }
        response = self.client.post(
            "/api/industry/orders",
            data=json.dumps(body),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 201, response.content)
        order_id = response.json()["order_id"]
        order = IndustryOrder.objects.get(pk=order_id)
        self.assertIsNotNone(order.profit_breakdown)
        self.assertIsNotNone(order.profit_breakdown_computed_at)

    @patch("industry.helpers.orders_profit_summary.plan_product_unit_cost")
    @patch(
        "industry.helpers.orders_profit_summary.jita_sell_prices_by_type_id"
    )
    def test_refresh_endpoint(self, mock_prices, mock_plan):
        mock_prices.return_value = {self.eve_type.id: 1_500_000}
        mock_plan.side_effect = lambda tid, **kw: self._unit_cost(
            tid, self.eve_type.name
        )
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
            location=self.location,
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=self.eve_type, quantity=2
        )
        ensure_order_profit_breakdown(order)

        response = self.client.post(
            f"/api/industry/orders/{order.pk}/profit-breakdown/refresh",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["rows"][0]["qty"], 2)

        order.fulfilled_at = timezone.now()
        order.save(update_fields=["fulfilled_at"])
        response = self.client.post(
            f"/api/industry/orders/{order.pk}/profit-breakdown/refresh",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)

    def test_get_order_includes_refresh_flag(self):
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
            location=self.location,
        )
        response = self.client.get(f"/api/industry/orders/{order.pk}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["can_refresh_profit_breakdown"])
        self.assertIsNone(data["profit_breakdown_computed_at"])
