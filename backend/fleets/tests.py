import datetime
import logging

from django.db.models import signals
from django.test import Client

from app.test import TestCase
from eveonline.models import EveCharacter
from fleets.models import EveFleet, EveFleetAudience, EveFleetLocation

BASE_URL = "/api/fleets"

logger = logging.getLogger(__name__)


class FleetRouterTestCase(TestCase):
    """Test cases for the fleet router."""

    def setUp(self):
        # create test client
        self.client = Client()

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

        super().setUp()

    def test_patch_fleet(self):
        self.user.is_superuser = True
        self.user.save()

        aud = EveFleetAudience.objects.create(
            name="Test Audience",
        )
        loc = EveFleetLocation.objects.create(
            location_id=123,
            location_name="Test Location",
            solar_system_id=234,
            solar_system_name="Somewhere",
        )

        fleet = EveFleet.objects.create(
            start_time=datetime.datetime.now(),
            description="Test fleet",
            type="training",
            created_by=self.user,
            audience=aud,
            location=loc,
        )

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
