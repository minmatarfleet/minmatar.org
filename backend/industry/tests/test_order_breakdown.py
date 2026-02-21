"""Tests for GET /orders/{id}/breakdown, GET /orders/{id}/orderitems/{id}/breakdown, GET .../assignments/breakdown."""

from unittest.mock import patch

from datetime import timedelta

from django.test import Client
from django.utils import timezone

from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter, EveLocation
from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase as AppTestCase
from industry.models import (
    IndustryOrder,
    IndustryOrderItem,
    IndustryOrderItemAssignment,
)


def _mock_breakdown_for_product(
    eve_type, quantity=1, max_depth=None, store=True
):
    """Return a minimal nested breakdown tree (no SDE/ESI)."""
    return {
        "name": eve_type.name,
        "type_id": eve_type.id,
        "quantity": quantity,
        "source": "raw",
        "depth": 0,
        "children": [],
    }


class OrderBreakdownTestCase(AppTestCase):
    """Tests for order and order-item breakdown endpoints (public)."""

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
            character_id=999001,
            defaults={"character_name": "Test Char", "user": self.user},
        )[0]
        set_primary_character(self.user, self.character)
        self.eve_type = EveType.objects.create(
            id=999201,
            name="Test Mineral",
            published=True,
            eve_group=self.eve_group,
        )
        self.location = EveLocation.objects.create(
            location_id=1999001,
            location_name="Test Station",
            solar_system_id=300001,
            solar_system_name="Test System",
            short_name="TST",
        )
        self.order = IndustryOrder.objects.create(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
            location=self.location,
        )
        self.order_item = IndustryOrderItem.objects.create(
            order=self.order,
            eve_type=self.eve_type,
            quantity=5,
        )

    @patch(
        "industry.helpers.type_breakdown.get_breakdown_for_industry_product"
    )
    def test_get_order_breakdown_returns_200_with_roots(self, mock_breakdown):
        mock_breakdown.side_effect = _mock_breakdown_for_product
        response = self.client.get(
            f"/api/industry/orders/{self.order.pk}/breakdown",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("roots", data)
        self.assertEqual(len(data["roots"]), 1)
        self.assertEqual(data["roots"][0]["name"], self.eve_type.name)
        self.assertEqual(data["roots"][0]["type_id"], self.eve_type.id)
        self.assertEqual(data["roots"][0]["quantity"], 5)
        self.assertIn("industry_product_id", data["roots"][0])

    def test_get_order_breakdown_returns_404_when_order_not_found(self):
        response = self.client.get(
            "/api/industry/orders/999999/breakdown",
        )
        self.assertEqual(response.status_code, 404)

    @patch(
        "industry.helpers.type_breakdown.get_breakdown_for_industry_product"
    )
    def test_get_order_item_breakdown_returns_200_with_tree(
        self, mock_breakdown
    ):
        mock_breakdown.side_effect = _mock_breakdown_for_product
        response = self.client.get(
            f"/api/industry/orders/{self.order.pk}/orderitems/{self.order_item.pk}/breakdown",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], self.eve_type.name)
        self.assertEqual(data["type_id"], self.eve_type.id)
        self.assertEqual(data["quantity"], 5)
        self.assertIn("children", data)
        self.assertIn("industry_product_id", data)

    def test_get_order_item_breakdown_returns_404_when_item_not_found(self):
        response = self.client.get(
            f"/api/industry/orders/{self.order.pk}/orderitems/999999/breakdown",
        )
        self.assertEqual(response.status_code, 404)

    @patch(
        "industry.helpers.type_breakdown.get_breakdown_for_industry_product"
    )
    def test_get_order_item_assignments_breakdown_returns_200(
        self, mock_breakdown
    ):
        mock_breakdown.side_effect = _mock_breakdown_for_product
        assignee = EveCharacter.objects.create(
            character_id=999020,
            character_name="Assignee",
            user=self.user,
        )
        IndustryOrderItemAssignment.objects.create(
            order_item=self.order_item,
            character=assignee,
            quantity=2,
        )
        response = self.client.get(
            f"/api/industry/orders/{self.order.pk}/orderitems/{self.order_item.pk}/assignments/breakdown",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("assignments", data)
        self.assertEqual(len(data["assignments"]), 1)
        self.assertEqual(
            data["assignments"][0]["character_id"], assignee.character_id
        )
        self.assertEqual(
            data["assignments"][0]["character_name"], assignee.character_name
        )
        self.assertEqual(data["assignments"][0]["quantity"], 2)
        self.assertIn("breakdown", data["assignments"][0])
        self.assertEqual(data["assignments"][0]["breakdown"]["quantity"], 2)

    def test_get_order_item_assignments_breakdown_returns_404_when_item_not_found(
        self,
    ):
        response = self.client.get(
            f"/api/industry/orders/{self.order.pk}/orderitems/999999/assignments/breakdown",
        )
        self.assertEqual(response.status_code, 404)
