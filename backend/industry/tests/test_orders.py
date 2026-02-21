"""Tests for industry orders endpoints: GET /orders, GET /orders/{id} (public)."""

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


class OrdersEndpointTestCase(AppTestCase):
    """Tests for GET /api/industry/orders and GET /api/industry/orders/{id} (public, no auth)."""

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

    def test_get_orders_returns_list_with_location(self):
        order = IndustryOrder.objects.create(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
            location=self.location,
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=self.eve_type, quantity=2
        )
        response = self.client.get("/api/industry/orders")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], order.pk)
        self.assertEqual(
            data[0]["character_name"], self.character.character_name
        )
        self.assertIsNotNone(data[0]["location"])
        self.assertEqual(
            data[0]["location"]["location_id"], self.location.location_id
        )
        self.assertEqual(
            data[0]["location"]["location_name"], self.location.location_name
        )

    def test_get_orders_returns_empty_when_none(self):
        response = self.client.get("/api/industry/orders")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_get_orders_returns_all_orders_public(self):
        """List includes orders from any user (public endpoint)."""
        other_user = self.user.__class__.objects.create(username="other")
        other_char = EveCharacter.objects.create(
            character_id=999005,
            character_name="Other Owner",
            user=other_user,
        )
        order1 = IndustryOrder.objects.create(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
        )
        order2 = IndustryOrder.objects.create(
            needed_by=(timezone.now() + timedelta(days=14)).date(),
            character=other_char,
        )
        response = self.client.get("/api/industry/orders")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        ids = {o["id"] for o in data}
        self.assertEqual(ids, {order1.pk, order2.pk})

    def test_get_order_returns_detail_with_items_and_assignments(self):
        order = IndustryOrder.objects.create(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
            location=self.location,
        )
        item = IndustryOrderItem.objects.create(
            order=order, eve_type=self.eve_type, quantity=5
        )
        assignee = EveCharacter.objects.create(
            character_id=999004,
            character_name="Assignee Char",
            user=self.user,
        )
        IndustryOrderItemAssignment.objects.create(
            order_item=item, character=assignee, quantity=3
        )
        response = self.client.get(f"/api/industry/orders/{order.pk}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], order.pk)
        self.assertEqual(data["character_name"], self.character.character_name)
        self.assertEqual(
            data["location"]["location_name"], self.location.location_name
        )
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["eve_type_id"], self.eve_type.id)
        self.assertEqual(data["items"][0]["eve_type_name"], self.eve_type.name)
        self.assertEqual(data["items"][0]["quantity"], 5)
        self.assertEqual(len(data["items"][0]["assignments"]), 1)
        self.assertEqual(
            data["items"][0]["assignments"][0]["character_name"],
            assignee.character_name,
        )
        self.assertEqual(data["items"][0]["assignments"][0]["quantity"], 3)

    def test_get_order_orderitems_returns_items_with_assignments(self):
        order = IndustryOrder.objects.create(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
            location=self.location,
        )
        item = IndustryOrderItem.objects.create(
            order=order, eve_type=self.eve_type, quantity=4
        )
        assignee = EveCharacter.objects.create(
            character_id=999007,
            character_name="Orderitems Assignee",
            user=self.user,
        )
        IndustryOrderItemAssignment.objects.create(
            order_item=item, character=assignee, quantity=2
        )
        response = self.client.get(
            f"/api/industry/orders/{order.pk}/orderitems"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], item.pk)
        self.assertEqual(data[0]["eve_type_id"], self.eve_type.id)
        self.assertEqual(data[0]["quantity"], 4)
        self.assertEqual(len(data[0]["assignments"]), 1)
        self.assertEqual(
            data[0]["assignments"][0]["character_name"],
            assignee.character_name,
        )
        self.assertEqual(data[0]["assignments"][0]["quantity"], 2)

    def test_get_order_orderitems_returns_404_when_order_not_found(self):
        response = self.client.get("/api/industry/orders/999999/orderitems")
        self.assertEqual(response.status_code, 404)

    def test_get_order_returns_200_for_any_order_public(self):
        """Single order can be viewed by anyone (public endpoint)."""
        other_user = self.user.__class__.objects.create(username="other2")
        other_char = EveCharacter.objects.create(
            character_id=999006,
            character_name="Other Owner 2",
            user=other_user,
        )
        order = IndustryOrder.objects.create(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=other_char,
        )
        response = self.client.get(f"/api/industry/orders/{order.pk}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], order.pk)
        self.assertEqual(data["character_name"], other_char.character_name)

    def test_get_order_returns_404_when_not_found(self):
        response = self.client.get("/api/industry/orders/999999")
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"])
