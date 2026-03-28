"""Tests for industry orders endpoints: GET /orders, GET /orders/{id} (public)."""

import json
from datetime import timedelta
from decimal import Decimal

import jwt
from django.conf import settings
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
from industry.test_utils import create_industry_order


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
        order = create_industry_order(
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
        self.assertEqual(len(data[0]["items"]), 1)
        self.assertEqual(data[0]["items"][0]["eve_type_id"], self.eve_type.id)
        self.assertEqual(
            data[0]["items"][0]["eve_type_name"], self.eve_type.name
        )
        self.assertEqual(data[0]["items"][0]["quantity"], 2)
        self.assertEqual(data[0]["assigned_to"], [])
        self.assertEqual(data[0]["public_short_code"], order.public_short_code)

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
        order1 = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
        )
        order2 = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=14)).date(),
            character=other_char,
        )
        response = self.client.get("/api/industry/orders")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        ids = {o["id"] for o in data}
        self.assertEqual(ids, {order1.pk, order2.pk})

    def test_get_orders_includes_flat_items_and_assigned_to(self):
        """List response includes items (type + quantity) and unique assignees."""
        assignee = EveCharacter.objects.create(
            character_id=999006,
            character_name="Builder One",
            user=self.user,
        )
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
            location=self.location,
        )
        item1 = IndustryOrderItem.objects.create(
            order=order, eve_type=self.eve_type, quantity=10
        )
        eve_type2 = EveType.objects.create(
            id=999202,
            name="Test Alloy",
            published=True,
            eve_group=self.eve_group,
        )
        item2 = IndustryOrderItem.objects.create(
            order=order, eve_type=eve_type2, quantity=5
        )
        IndustryOrderItemAssignment.objects.create(
            order_item=item1, character=assignee, quantity=10
        )
        IndustryOrderItemAssignment.objects.create(
            order_item=item2, character=assignee, quantity=5
        )
        response = self.client.get("/api/industry/orders")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(len(data[0]["items"]), 2)
        by_type = {it["eve_type_id"]: it for it in data[0]["items"]}
        self.assertEqual(
            by_type[self.eve_type.id]["eve_type_name"], "Test Mineral"
        )
        self.assertEqual(by_type[self.eve_type.id]["quantity"], 10)
        self.assertEqual(by_type[eve_type2.id]["eve_type_name"], "Test Alloy")
        self.assertEqual(by_type[eve_type2.id]["quantity"], 5)
        self.assertEqual(len(data[0]["assigned_to"]), 1)
        self.assertEqual(data[0]["assigned_to"][0]["character_id"], 999006)
        self.assertEqual(
            data[0]["assigned_to"][0]["character_name"], "Builder One"
        )

    def test_get_orders_items_include_assignment_targets(self):
        assignee = EveCharacter.objects.create(
            character_id=999007,
            character_name="Target Builder",
            user=self.user,
        )
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
            location=self.location,
        )
        item = IndustryOrderItem.objects.create(
            order=order, eve_type=self.eve_type, quantity=3
        )
        IndustryOrderItemAssignment.objects.create(
            order_item=item,
            character=assignee,
            quantity=3,
            target_unit_price=Decimal("1234567.50"),
            target_estimated_margin=Decimal("89000"),
        )
        response = self.client.get("/api/industry/orders")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data[0]["items"]), 1)
        row = data[0]["items"][0]
        self.assertEqual(row["eve_type_id"], self.eve_type.id)
        self.assertEqual(row["target_unit_price"], "1234567.50")
        self.assertEqual(row["target_estimated_margin"], "89000.00")

    def test_get_orders_items_use_line_targets_when_set(self):
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
            location=self.location,
        )
        IndustryOrderItem.objects.create(
            order=order,
            eve_type=self.eve_type,
            quantity=2,
            target_unit_price=Decimal("500000.00"),
            target_estimated_margin=Decimal("10000.00"),
        )
        response = self.client.get("/api/industry/orders")
        self.assertEqual(response.status_code, 200)
        row = response.json()[0]["items"][0]
        self.assertEqual(row["target_unit_price"], "500000.00")
        self.assertEqual(row["target_estimated_margin"], "10000.00")

    def test_get_order_returns_detail_with_items_and_assignments(self):
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
            location=self.location,
        )
        item = IndustryOrderItem.objects.create(
            order=order,
            eve_type=self.eve_type,
            quantity=5,
            target_unit_price=Decimal("99.50"),
            target_estimated_margin=Decimal("1.25"),
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
        self.assertEqual(data["items"][0]["target_unit_price"], "99.50")
        self.assertEqual(data["items"][0]["target_estimated_margin"], "1.25")
        self.assertEqual(len(data["items"][0]["assignments"]), 1)
        self.assertEqual(
            data["items"][0]["assignments"][0]["character_name"],
            assignee.character_name,
        )
        self.assertEqual(data["items"][0]["assignments"][0]["quantity"], 3)

    def test_get_order_orderitems_returns_items_with_assignments(self):
        order = create_industry_order(
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
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=other_char,
        )
        response = self.client.get(f"/api/industry/orders/{order.pk}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], order.pk)
        self.assertEqual(data["character_name"], other_char.character_name)
        self.assertEqual(data["public_short_code"], order.public_short_code)

    def test_get_order_returns_404_when_not_found(self):
        response = self.client.get("/api/industry/orders/999999")
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"])


class OrderMutationApiTests(OrdersEndpointTestCase):
    """Authenticated POST/PATCH/DELETE on industry orders."""

    def test_post_assignment_creates_row(self):
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
        )
        item = IndustryOrderItem.objects.create(
            order=order, eve_type=self.eve_type, quantity=5
        )
        assignee = EveCharacter.objects.create(
            character_id=999030,
            character_name="Assign Self",
            user=self.user,
        )
        url = (
            f"/api/industry/orders/{order.pk}/orderitems/{item.pk}/assignments"
        )
        response = self.client.post(
            url,
            data=json.dumps(
                {"character_id": assignee.character_id, "quantity": 2}
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertEqual(data["quantity"], 2)
        self.assertEqual(data["character_id"], assignee.character_id)

    def test_post_assignment_rejects_over_remaining(self):
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
        )
        item = IndustryOrderItem.objects.create(
            order=order, eve_type=self.eve_type, quantity=2
        )
        assignee = EveCharacter.objects.create(
            character_id=999031,
            character_name="Over Qty",
            user=self.user,
        )
        url = (
            f"/api/industry/orders/{order.pk}/orderitems/{item.pk}/assignments"
        )
        response = self.client.post(
            url,
            data=json.dumps(
                {"character_id": assignee.character_id, "quantity": 3}
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)

    def test_post_assignment_rejects_other_users_character(self):
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
        )
        item = IndustryOrderItem.objects.create(
            order=order, eve_type=self.eve_type, quantity=5
        )
        other = self.user.__class__.objects.create(username="other_assign")
        other_char = EveCharacter.objects.create(
            character_id=999032,
            character_name="Not Yours",
            user=other,
        )
        url = (
            f"/api/industry/orders/{order.pk}/orderitems/{item.pk}/assignments"
        )
        response = self.client.post(
            url,
            data=json.dumps(
                {"character_id": other_char.character_id, "quantity": 1}
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_post_assignment_self_assign_maximum_in_48h_window(self):
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
        )
        item = IndustryOrderItem.objects.create(
            order=order,
            eve_type=self.eve_type,
            quantity=10,
            self_assign_maximum=5,
        )
        assignee = EveCharacter.objects.create(
            character_id=999033,
            character_name="Capped Builder",
            user=self.user,
        )
        url = (
            f"/api/industry/orders/{order.pk}/orderitems/{item.pk}/assignments"
        )
        r1 = self.client.post(
            url,
            data=json.dumps(
                {"character_id": assignee.character_id, "quantity": 5}
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(r1.status_code, 201)
        r2 = self.client.post(
            url,
            data=json.dumps(
                {"character_id": assignee.character_id, "quantity": 1}
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(r2.status_code, 400)

    def test_post_assignment_after_48h_ignores_self_assign_maximum(self):
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
        )
        item = IndustryOrderItem.objects.create(
            order=order,
            eve_type=self.eve_type,
            quantity=10,
            self_assign_maximum=5,
        )
        assignee = EveCharacter.objects.create(
            character_id=999034,
            character_name="Late Builder",
            user=self.user,
        )
        old = timezone.now() - timedelta(hours=49)
        IndustryOrder.objects.filter(pk=order.pk).update(created_at=old)
        url = (
            f"/api/industry/orders/{order.pk}/orderitems/{item.pk}/assignments"
        )
        r1 = self.client.post(
            url,
            data=json.dumps(
                {"character_id": assignee.character_id, "quantity": 7}
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(r1.status_code, 201)
        r2 = self.client.post(
            url,
            data=json.dumps(
                {"character_id": assignee.character_id, "quantity": 3}
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(r2.status_code, 201)

    def test_patch_assignment_delivered_assignee_and_owner(self):
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
        )
        item = IndustryOrderItem.objects.create(
            order=order, eve_type=self.eve_type, quantity=5
        )
        assignee_user = self.user.__class__.objects.create(
            username="assignee_owner_test"
        )
        assignee = EveCharacter.objects.create(
            character_id=999035,
            character_name="Deliveree",
            user=assignee_user,
        )
        assignee_token = jwt.encode(
            {"user_id": assignee_user.id},
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        a = IndustryOrderItemAssignment.objects.create(
            order_item=item, character=assignee, quantity=2
        )
        url = f"/api/industry/orders/{order.pk}/orderitems/{item.pk}/assignments/{a.pk}"
        r = self.client.patch(
            url,
            data=json.dumps({"delivered": True}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {assignee_token}",
        )
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(r.json().get("delivered_at"))

        r2 = self.client.patch(
            url,
            data=json.dumps({"delivered": False}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {assignee_token}",
        )
        self.assertEqual(r2.status_code, 200)
        self.assertIsNone(r2.json().get("delivered_at"))

        r3 = self.client.patch(
            url,
            data=json.dumps({"delivered": True}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(r3.status_code, 200)

    def test_patch_assignment_delivered_forbidden_for_stranger(self):
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
        )
        item = IndustryOrderItem.objects.create(
            order=order, eve_type=self.eve_type, quantity=5
        )
        assignee = EveCharacter.objects.create(
            character_id=999036,
            character_name="Assignee Only",
            user=self.user,
        )
        a = IndustryOrderItemAssignment.objects.create(
            order_item=item, character=assignee, quantity=1
        )
        stranger = self.user.__class__.objects.create(username="stranger_ind")
        payload = jwt.encode(
            {"user_id": stranger.id},
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        url = f"/api/industry/orders/{order.pk}/orderitems/{item.pk}/assignments/{a.pk}"
        r = self.client.patch(
            url,
            data=json.dumps({"delivered": True}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {payload}",
        )
        self.assertEqual(r.status_code, 403)

    def test_post_create_order_and_delete(self):
        needed = (timezone.now() + timedelta(days=14)).date().isoformat()
        body = {
            "needed_by": needed,
            "character_id": self.character.character_id,
            "contract_to": "ACME Corp",
            "items": [
                {
                    "eve_type_id": self.eve_type.id,
                    "quantity": 3,
                    "self_assign_maximum": 2,
                },
            ],
        }
        r = self.client.post(
            "/api/industry/orders",
            data=json.dumps(body),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(r.status_code, 201, r.content)
        data = r.json()
        self.assertEqual(len(data["public_short_code"]), 3)
        self.assertNotIn("order_identifier", data)
        oid = data["order_id"]
        order = IndustryOrder.objects.get(pk=oid)
        self.assertEqual(data["public_short_code"], order.public_short_code)
        self.assertEqual(order.contract_to, "ACME Corp")
        self.assertEqual(order.items.get().self_assign_maximum, 2)

        r_del = self.client.delete(
            f"/api/industry/orders/{oid}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(r_del.status_code, 204)
        self.assertFalse(IndustryOrder.objects.filter(pk=oid).exists())

    def test_post_create_two_orders_distinct_public_short_codes(self):
        needed = (timezone.now() + timedelta(days=14)).date().isoformat()
        base = {
            "needed_by": needed,
            "character_id": self.character.character_id,
            "items": [{"eve_type_id": self.eve_type.id, "quantity": 1}],
        }
        r1 = self.client.post(
            "/api/industry/orders",
            data=json.dumps(base),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        r2 = self.client.post(
            "/api/industry/orders",
            data=json.dumps(base),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        c1 = r1.json()["public_short_code"]
        c2 = r2.json()["public_short_code"]
        self.assertNotEqual(c1, c2)
