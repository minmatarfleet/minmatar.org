"""Tests for industry orders endpoints: GET /orders, GET /orders/{id}, POST /orders, DELETE /orders/{id}."""

from datetime import timedelta

from django.test import Client
from django.utils import timezone

from eveonline.helpers.characters import set_primary_character, user_player
from eveonline.models import EveCharacter, EveLocation
from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase as AppTestCase
from industry.models import (
    IndustryOrder,
    IndustryOrderItem,
    IndustryOrderItemAssignment,
)


class OrdersEndpointTestCase(AppTestCase):
    """Tests for GET/POST/DELETE /api/industry/orders and GET/DELETE /api/industry/orders/{id}."""

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

    def _auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    def test_post_orders_creates_order_with_primary_character(self):
        needed_by = (timezone.now() + timedelta(days=7)).date().isoformat()
        payload = {
            "needed_by": needed_by,
            "items": [{"eve_type_id": self.eve_type.id, "quantity": 3}],
        }
        response = self.client.post(
            "/api/industry/orders",
            payload,
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("order_id", data)
        order = IndustryOrder.objects.get(pk=data["order_id"])
        self.assertEqual(order.character, self.character)
        self.assertEqual(order.needed_by.isoformat(), needed_by)
        items = list(order.items.all())
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].eve_type_id, self.eve_type.id)
        self.assertEqual(items[0].quantity, 3)

    def test_post_orders_with_character_id(self):
        needed_by = (timezone.now() + timedelta(days=14)).date().isoformat()
        payload = {
            "needed_by": needed_by,
            "character_id": self.character.character_id,
            "items": [{"eve_type_id": self.eve_type.id, "quantity": 1}],
        }
        response = self.client.post(
            "/api/industry/orders",
            payload,
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        order = IndustryOrder.objects.get(pk=data["order_id"])
        self.assertEqual(order.character, self.character)

    def test_post_orders_with_location_id(self):
        needed_by = (timezone.now() + timedelta(days=7)).date().isoformat()
        payload = {
            "needed_by": needed_by,
            "location_id": self.location.location_id,
            "items": [{"eve_type_id": self.eve_type.id, "quantity": 2}],
        }
        response = self.client.post(
            "/api/industry/orders",
            payload,
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 201)
        order = IndustryOrder.objects.get(pk=response.json()["order_id"])
        self.assertEqual(order.location_id, self.location.location_id)

    def test_post_orders_invalid_location_id_returns_404(self):
        needed_by = (timezone.now() + timedelta(days=7)).date().isoformat()
        payload = {
            "needed_by": needed_by,
            "location_id": 999999999,
            "items": [{"eve_type_id": self.eve_type.id, "quantity": 1}],
        }
        response = self.client.post(
            "/api/industry/orders",
            payload,
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 404)

    def test_post_orders_unauthorized_without_token(self):
        payload = {
            "needed_by": (timezone.now() + timedelta(days=7))
            .date()
            .isoformat(),
            "items": [{"eve_type_id": self.eve_type.id, "quantity": 1}],
        }
        response = self.client.post(
            "/api/industry/orders",
            payload,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_post_orders_forbidden_for_other_users_character(self):
        other_char = EveCharacter.objects.create(
            character_id=999002,
            character_name="Other Char",
            user=None,
        )
        payload = {
            "needed_by": (timezone.now() + timedelta(days=7))
            .date()
            .isoformat(),
            "character_id": other_char.character_id,
            "items": [{"eve_type_id": self.eve_type.id, "quantity": 1}],
        }
        response = self.client.post(
            "/api/industry/orders",
            payload,
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("own characters", response.json()["detail"])

    def test_post_orders_no_primary_returns_400(self):
        # Clear primary so user has no primary character
        player = user_player(self.user)
        if player:
            player.primary_character = None
            player.save()
        payload = {
            "needed_by": (timezone.now() + timedelta(days=7))
            .date()
            .isoformat(),
            "items": [{"eve_type_id": self.eve_type.id, "quantity": 1}],
        }
        response = self.client.post(
            "/api/industry/orders",
            payload,
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("primary character", response.json()["detail"])
        set_primary_character(self.user, self.character)

    def test_post_orders_empty_items_returns_400(self):
        payload = {
            "needed_by": (timezone.now() + timedelta(days=7))
            .date()
            .isoformat(),
            "character_id": self.character.character_id,
            "items": [],
        }
        response = self.client.post(
            "/api/industry/orders",
            payload,
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("At least one", response.json()["detail"])

    def test_post_orders_unknown_type_returns_404(self):
        payload = {
            "needed_by": (timezone.now() + timedelta(days=7))
            .date()
            .isoformat(),
            "character_id": self.character.character_id,
            "items": [{"eve_type_id": 99999999, "quantity": 1}],
        }
        response = self.client.post(
            "/api/industry/orders",
            payload,
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"])

    def test_delete_order_returns_204_when_owner(self):
        order = IndustryOrder.objects.create(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=self.eve_type, quantity=1
        )
        response = self.client.delete(
            f"/api/industry/orders/{order.pk}",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(IndustryOrder.objects.filter(pk=order.pk).exists())

    def test_delete_order_returns_403_when_not_owner(self):
        other_user = self.user.__class__.objects.create(username="other")
        other_char = EveCharacter.objects.create(
            character_id=999003,
            character_name="Other Owner",
            user=other_user,
        )
        order = IndustryOrder.objects.create(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=other_char,
        )
        response = self.client.delete(
            f"/api/industry/orders/{order.pk}",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("own characters", response.json()["detail"])
        self.assertTrue(IndustryOrder.objects.filter(pk=order.pk).exists())

    def test_delete_order_returns_404_when_not_found(self):
        response = self.client.delete(
            "/api/industry/orders/999999",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"])

    def test_delete_order_unauthorized_without_token(self):
        order = IndustryOrder.objects.create(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
        )
        response = self.client.delete(f"/api/industry/orders/{order.pk}")
        self.assertEqual(response.status_code, 401)

    def test_get_orders_returns_list_with_location(self):
        order = IndustryOrder.objects.create(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
            location=self.location,
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=self.eve_type, quantity=2
        )
        response = self.client.get(
            "/api/industry/orders",
            **self._auth_headers(),
        )
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
        response = self.client.get(
            "/api/industry/orders",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_get_orders_unauthorized_without_token(self):
        response = self.client.get("/api/industry/orders")
        self.assertEqual(response.status_code, 401)

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
        response = self.client.get(
            f"/api/industry/orders/{order.pk}",
            **self._auth_headers(),
        )
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

    def test_get_order_returns_403_when_not_owner(self):
        other_user = self.user.__class__.objects.create(username="other2")
        other_char = EveCharacter.objects.create(
            character_id=999005,
            character_name="Other Owner 2",
            user=other_user,
        )
        order = IndustryOrder.objects.create(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=other_char,
        )
        response = self.client.get(
            f"/api/industry/orders/{order.pk}",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("own characters", response.json()["detail"])

    def test_get_order_returns_404_when_not_found(self):
        response = self.client.get(
            "/api/industry/orders/999999",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"])
