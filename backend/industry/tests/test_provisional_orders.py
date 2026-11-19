"""Provisional industry orders: claiming window, start, and unfulfilled import."""

import json
from datetime import timedelta

from django.utils import timezone
from eveuniverse.models import EveType

from groups.helpers.feature_access import clear_feature_cache
from groups.management.commands.sync_pilot_features import (
    Command as SyncPilotFeaturesCommand,
)
from groups.models import PilotFeature
from industry.helpers.provisional import start_provisional_order
from industry.models import (
    IndustryOrder,
    IndustryOrderItem,
    IndustryOrderItemAssignment,
    IndustryOrderUnfulfilledItem,
)
from industry.test_utils import create_industry_order
from industry.tests.test_orders import OrdersEndpointTestCase
from tribes.models import Tribe, TribeGroup


class ProvisionalOrderApiTests(OrdersEndpointTestCase):
    def setUp(self):
        super().setUp()
        tribe = Tribe.objects.create(
            name="Industry", slug="industry-provisional", chief=self.user
        )
        tribe_group = TribeGroup.objects.create(
            tribe=tribe, name="Mining", code="industry.mining.provisional"
        )
        SyncPilotFeaturesCommand().handle()
        feature = PilotFeature.objects.get(code="industry.order.submit")
        feature.tribe_groups.set([tribe_group])
        PilotFeature.objects.get(
            code="industry.order.manage"
        ).tribe_groups.set([tribe_group])
        clear_feature_cache()
        self.guardian = EveType.objects.create(
            id=999301,
            name="Guardian",
            published=True,
            eve_group=self.eve_group,
        )
        self.rifter = EveType.objects.create(
            id=999302,
            name="Rifter",
            published=True,
            eve_group=self.eve_group,
        )

    def _post_order(self, body):
        return self.client.post(
            "/api/industry/orders",
            data=json.dumps(body),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

    def _create_body(self, **overrides):
        needed = (timezone.now() + timedelta(days=14)).date().isoformat()
        starts = (timezone.now() + timedelta(hours=36)).isoformat()
        body = {
            "needed_by": needed,
            "character_id": self.character.character_id,
            "location_id": self.location.location_id,
            "contract_to": self.character.character_name,
            "starts_at": starts,
            "items": [
                {"eve_type_id": self.guardian.id, "quantity": 100},
                {"eve_type_id": self.rifter.id, "quantity": 10},
            ],
        }
        body.update(overrides)
        return body

    def test_create_provisional_order_exposes_claiming_window(self):
        response = self._post_order(self._create_body())
        self.assertEqual(response.status_code, 201, response.content)
        order = IndustryOrder.objects.get(pk=response.json()["order_id"])
        self.assertIsNotNone(order.starts_at)
        self.assertIsNone(order.started_at)

        detail = self.client.get(f"/api/industry/orders/{order.pk}")
        self.assertEqual(detail.status_code, 200)
        data = detail.json()
        self.assertTrue(data["provisional"])
        self.assertIsNotNone(data["starts_at"])
        self.assertEqual(
            data["location"]["location_name"], self.location.location_name
        )
        self.assertTrue(data["items"][0]["provisional"])

        listing = self.client.get("/api/industry/orders")
        row = next(item for item in listing.json() if item["id"] == order.pk)
        self.assertTrue(row["provisional"])

    def test_create_rejects_start_in_the_past(self):
        past = (timezone.now() - timedelta(hours=1)).isoformat()
        response = self._post_order(self._create_body(starts_at=past))
        self.assertEqual(response.status_code, 400)
        self.assertIn("future", response.json()["detail"])

    def test_create_rejects_start_after_needed_by(self):
        late = (timezone.now() + timedelta(days=20)).isoformat()
        response = self._post_order(self._create_body(starts_at=late))
        self.assertEqual(response.status_code, 400)
        self.assertIn("needed-by", response.json()["detail"])

    def test_claim_cap_holds_for_the_whole_provisional_period(self):
        response = self._post_order(
            self._create_body(
                starts_at=(timezone.now() + timedelta(hours=72)).isoformat(),
                items=[
                    {
                        "eve_type_id": self.guardian.id,
                        "quantity": 100,
                        "self_assign_maximum": 2,
                    }
                ],
            )
        )
        self.assertEqual(response.status_code, 201, response.content)
        order = IndustryOrder.objects.get(pk=response.json()["order_id"])
        item = order.items.get()
        url = (
            f"/api/industry/orders/{order.pk}/orderitems/{item.pk}/assignments"
        )
        claim = self.client.post(
            url,
            data=json.dumps(
                {"character_id": self.character.character_id, "quantity": 3}
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(claim.status_code, 400, claim.content)
        self.assertIn("Until this order starts", claim.json()["detail"])

    def test_start_drops_unclaimed_quantities(self):
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=14)).date(),
            character=self.character,
            location=self.location,
            starts_at=timezone.now() - timedelta(minutes=1),
        )
        guardians = IndustryOrderItem.objects.create(
            order=order, eve_type=self.guardian, quantity=100
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=self.rifter, quantity=10
        )
        IndustryOrderItemAssignment.objects.create(
            order_item=guardians, character=self.character, quantity=40
        )

        self.assertTrue(start_provisional_order(order.pk))
        order.refresh_from_db()
        self.assertIsNotNone(order.started_at)
        self.assertIsNotNone(order.selection_notified_at)
        guardians.refresh_from_db()
        self.assertEqual(guardians.quantity, 40)
        self.assertFalse(
            IndustryOrderItem.objects.filter(
                order=order, eve_type=self.rifter
            ).exists()
        )
        leftovers = {
            row.eve_type_id: row
            for row in IndustryOrderUnfulfilledItem.objects.filter(order=order)
        }
        self.assertEqual(leftovers[self.guardian.id].quantity, 60)
        self.assertEqual(leftovers[self.rifter.id].quantity, 10)
        self.assertIsNone(leftovers[self.guardian.id].imported_into_id)

        detail = self.client.get(f"/api/industry/orders/{order.pk}").json()
        self.assertFalse(detail["provisional"])
        self.assertEqual(len(detail["unfulfilled_items"]), 2)

        self.assertFalse(start_provisional_order(order.pk))
        self.assertEqual(
            IndustryOrderUnfulfilledItem.objects.filter(order=order).count(),
            2,
        )

    def test_import_unfulfilled_marks_only_the_lines_taken(self):
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=14)).date(),
            character=self.character,
            location=self.location,
            starts_at=timezone.now() - timedelta(minutes=1),
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=self.guardian, quantity=100
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=self.rifter, quantity=10
        )
        start_provisional_order(order.pk)

        response = self._post_order(
            {
                "needed_by": (timezone.now() + timedelta(days=14))
                .date()
                .isoformat(),
                "character_id": self.character.character_id,
                "location_id": self.location.location_id,
                "contract_to": self.character.character_name,
                "import_unfulfilled_from_order_id": order.pk,
                "items": [{"eve_type_id": self.guardian.id, "quantity": 60}],
            }
        )
        self.assertEqual(response.status_code, 201, response.content)
        new_id = response.json()["order_id"]
        guardian = IndustryOrderUnfulfilledItem.objects.get(
            order=order, eve_type=self.guardian
        )
        rifter = IndustryOrderUnfulfilledItem.objects.get(
            order=order, eve_type=self.rifter
        )
        self.assertEqual(guardian.imported_into_id, new_id)
        self.assertIsNone(rifter.imported_into_id)

    def test_import_requires_order_manager(self):
        PilotFeature.objects.get(
            code="industry.order.manage"
        ).tribe_groups.set([])
        clear_feature_cache()
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=14)).date(),
            character=self.character,
            location=self.location,
        )
        response = self._post_order(
            {
                "needed_by": (timezone.now() + timedelta(days=14))
                .date()
                .isoformat(),
                "character_id": self.character.character_id,
                "location_id": self.location.location_id,
                "contract_to": self.character.character_name,
                "import_unfulfilled_from_order_id": order.pk,
                "items": [{"eve_type_id": self.eve_type.id, "quantity": 1}],
            }
        )
        self.assertEqual(response.status_code, 403, response.content)
