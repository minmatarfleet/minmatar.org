import datetime
import logging

from django.db.models import signals
from django.test import Client

from app.test import TestCase
from eveonline.models import EveCharacter
from fleets.models import EveFleet, EveFleetAudience, EveFleetLocation
from fleets.router import fixup_fleet_status, EveFleetTrackingResponse

BASE_URL = "/api/fleets"

logger = logging.getLogger(__name__)


class FleetRouterTestCase(TestCase):
    """Test cases for the fleet router."""

    def setUp(self):
        # create test client
        self.client = Client()

        self.disconnect_signals()

        self.setup_reference_data()

        super().setUp()

    def setup_reference_data(self):
        """Create reference data needed for fleets"""
        self.audience = EveFleetAudience.objects.create(
            name="Test Audience",
        )
        self.location = EveFleetLocation.objects.create(
            location_id=123,
            location_name="Test Location",
            solar_system_id=234,
            solar_system_name="Somewhere",
        )

    def disconnect_signals(self):
        """Disconnect signals that would try to call Discord or ESI"""
        signals.post_save.disconnect(
            sender=EveFleet,
            dispatch_uid="update_fleet_schedule_on_save",
        )
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_private_data",
        )

    def make_test_fleet(
        self, description: str, start: datetime.datetime = None
    ) -> EveFleet:
        if start is None:
            start = datetime.datetime.now() + datetime.timedelta(hours=1)

        return EveFleet.objects.create(
            start_time=start,
            description=description,
            type="training",
            status="pending",
            created_by=self.user,
            audience=self.audience,
            location=self.location,
        )

    def test_get_fleets_v3(self):
        self.make_test_fleet("Test fleet 1")
        self.make_test_fleet("Test fleet 2")

        response = self.client.get(
            f"{BASE_URL}/v3?fleet_filter=upcoming",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        fleets = response.json()
        # logger.info("fleets v3 response = %s", fleets)
        self.assertEqual(2, len(fleets))

    def test_get_fleet(self):
        fleet = self.make_test_fleet("Test fleet")

        response = self.client.get(
            f"{BASE_URL}/{fleet.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(fleet.id, response.json()["id"])
        self.assertEqual("Test fleet", response.json()["description"])

    def test_patch_fleet(self):
        self.user.is_superuser = True
        self.user.save()

        fleet = self.make_test_fleet("Test fleet")

        logger.info("Created test fleet %d", fleet.id)

        self.assertEqual("Test fleet", fleet.description)

        update = {"description": "Updated"}

        response = self.client.patch(
            f"{BASE_URL}/{fleet.id}",
            update,
            "application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)

        updated_fleet = EveFleet.objects.filter(id=fleet.id).first()

        self.assertEqual("Updated", updated_fleet.description)

    def test_fixup_fleet_status(self):
        self.assertEqual(None, fixup_fleet_status(None, None))
        fleet = self.make_test_fleet("Test")
        fleet.status = "active"
        tracking = None
        self.assertEqual("active", fixup_fleet_status(fleet, tracking))
        tracking = EveFleetTrackingResponse(
            id=1,
            start_time=datetime.datetime.now(),
            end_time=datetime.datetime.now(),
            is_registered=True,
        )
        self.assertEqual("complete", fixup_fleet_status(fleet, tracking))
