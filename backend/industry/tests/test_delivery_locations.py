"""Orders delivered somewhere other than the staging, and who can claim."""

import json
import uuid
from datetime import timedelta

from django.test import Client
from django.utils import timezone
from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase
from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter, EveLocation
from groups.helpers.feature_access import clear_feature_cache
from groups.management.commands.sync_pilot_features import (
    Command as SyncPilotFeaturesCommand,
)
from groups.models import PilotFeature
from industry.models import (
    IndustryOrderItem,
    IndustryOrderItemAssignment,
    IndustryProduct,
    Strategy,
)
from industry.test_utils import create_industry_order
from onboarding.models import (
    OnboardingProgram,
    OnboardingProgramType,
    UserOnboardingAcknowledgment,
)
from tribes.models import Tribe, TribeGroup, TribeGroupMembership

AMAMAKE = 30002537
BUILDERS = 98000001


class DeliveryLocationTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        category, _ = EveCategory.objects.get_or_create(
            id=1, defaults={"name": "Test Category", "published": True}
        )
        group, _ = EveGroup.objects.get_or_create(
            id=1,
            defaults={
                "name": "Test Group",
                "published": True,
                "eve_category": category,
            },
        )
        self.eve_type = EveType.objects.create(
            id=999601, name="Produced Hull", published=True, eve_group=group
        )
        product = IndustryProduct.objects.create(
            eve_type=self.eve_type, strategy=Strategy.IMPORTED
        )
        IndustryProduct.objects.filter(pk=product.pk).update(
            strategy=Strategy.PRODUCED
        )
        self.main = EveCharacter.objects.create(
            character_id=999101,
            character_name="Main Pilot",
            user=self.user,
            corporation_id=98000099,
        )
        self.builder = EveCharacter.objects.create(
            character_id=999102,
            character_name="Builder Alt",
            user=self.user,
            corporation_id=BUILDERS,
        )
        set_primary_character(self.user, self.main)
        self.home = EveLocation.objects.create(
            location_id=1000000001,
            location_name="Amamake - Home Station",
            solar_system_id=AMAMAKE,
            solar_system_name="Amamake",
            short_name="Home",
            staging_active=True,
            industry_delivery=True,
        )
        self.forward = EveLocation.objects.create(
            location_id=1000000002,
            location_name="Jita - Forward Station",
            solar_system_id=30000142,
            solar_system_name="Jita",
            short_name="Forward",
            deployment_active=True,
            industry_delivery=True,
            dock_access=[
                {
                    "kind": "corporation",
                    "id": BUILDERS,
                    "name": "Example Builders",
                    "ticker": "EXB",
                }
            ],
        )
        self.elsewhere = EveLocation.objects.create(
            location_id=1000000003,
            location_name="Jita - Not For Orders",
            solar_system_id=30000142,
            solar_system_name="Jita",
            short_name="Elsewhere",
        )
        program, _ = OnboardingProgram.objects.get_or_create(
            program_type=OnboardingProgramType.ORDERS,
            defaults={"version": uuid.uuid4()},
        )
        UserOnboardingAcknowledgment.objects.update_or_create(
            user=self.user,
            program=program,
            defaults={"acknowledged_version": program.version},
        )

    def _auth(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    def _market_member(self):
        SyncPilotFeaturesCommand().handle()
        tribe = Tribe.objects.create(name="Supply", slug="supply-test")
        market = TribeGroup.objects.create(
            tribe=tribe, name="Market", code="supply.market"
        )
        PilotFeature.objects.get(
            code="industry.order.submit.produced"
        ).tribe_groups.set([market])
        TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=market,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        clear_feature_cache()

    def _create(self, location_id):
        return self.client.post(
            "/api/industry/orders",
            data=json.dumps(
                {
                    "needed_by": (timezone.now() + timedelta(days=14))
                    .date()
                    .isoformat(),
                    "character_id": self.main.character_id,
                    "location_id": location_id,
                    "contract_to": self.main.character_name,
                    "items": [
                        {"eve_type_id": self.eve_type.id, "quantity": 1}
                    ],
                }
            ),
            content_type="application/json",
            **self._auth(),
        )

    def _order_at(self, location):
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.main,
            location=location,
        )
        item = IndustryOrderItem.objects.create(
            order=order, eve_type=self.eve_type, quantity=5
        )
        return order, item

    def _claim(self, order, item, character):
        return self.client.post(
            f"/api/industry/orders/{order.pk}/orderitems/{item.pk}"
            "/assignments",
            data=json.dumps(
                {"character_id": character.character_id, "quantity": 1}
            ),
            content_type="application/json",
            **self._auth(),
        )

    def test_delivery_locations_list_staging_first(self):
        response = self.client.get(
            "/api/industry/orders/delivery-locations", **self._auth()
        )
        self.assertEqual(response.status_code, 200)
        rows = response.json()
        self.assertEqual([r["short_name"] for r in rows], ["Home", "Forward"])
        self.assertTrue(rows[0]["staging"])
        self.assertTrue(rows[0]["costed"])
        self.assertEqual(rows[0]["dock_tickers"], [])
        self.assertTrue(rows[1]["deployment"])
        self.assertFalse(rows[1]["costed"])
        self.assertEqual(rows[1]["dock_tickers"], ["EXB"])

    def test_create_order_to_a_delivery_location(self):
        self._market_member()
        response = self._create(self.forward.location_id)
        self.assertEqual(response.status_code, 201, response.content)

    def test_create_order_rejects_a_location_without_delivery(self):
        self._market_member()
        response = self._create(self.elsewhere.location_id)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("Industry delivery", response.json()["detail"])

    def test_order_detail_describes_the_location(self):
        order, _ = self._order_at(self.forward)
        location = self.client.get(f"/api/industry/orders/{order.pk}").json()[
            "location"
        ]
        self.assertEqual(location["short_name"], "Forward")
        self.assertFalse(location["costed"])
        self.assertEqual(location["dock_tickers"], ["EXB"])

    def test_claim_rejected_for_a_character_that_cannot_dock(self):
        order, item = self._order_at(self.forward)
        response = self._claim(order, item, self.main)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("can't dock at Forward", response.json()["detail"])
        self.assertFalse(IndustryOrderItemAssignment.objects.exists())

    def test_claim_accepted_for_a_character_that_can_dock(self):
        order, item = self._order_at(self.forward)
        response = self._claim(order, item, self.builder)
        self.assertEqual(response.status_code, 201, response.content)

    def test_claim_at_an_open_location_takes_anyone(self):
        order, item = self._order_at(self.home)
        response = self._claim(order, item, self.main)
        self.assertEqual(response.status_code, 201, response.content)

    def test_claim_characters_lists_who_can_dock(self):
        order, _ = self._order_at(self.forward)
        data = self.client.get(
            f"/api/industry/orders/{order.pk}/claim-characters",
            **self._auth(),
        ).json()
        self.assertTrue(data["restricted"])
        self.assertEqual(data["location_name"], "Forward")
        self.assertEqual(
            [c["character_name"] for c in data["characters"]],
            ["Builder Alt"],
        )

        order, _ = self._order_at(self.home)
        data = self.client.get(
            f"/api/industry/orders/{order.pk}/claim-characters",
            **self._auth(),
        ).json()
        self.assertFalse(data["restricted"])
        self.assertEqual(
            [c["character_name"] for c in data["characters"]],
            ["Main Pilot", "Builder Alt"],
        )
        self.assertTrue(data["characters"][0]["is_primary"])
