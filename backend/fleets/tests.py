import datetime
import logging
from unittest.mock import patch

from django.db.models import signals
from django.test import Client, SimpleTestCase
from django.contrib.auth.models import User

from app.test import TestCase
from eveonline.models import EveCharacter, EvePrimaryCharacter
from discord.models import DiscordUser
from fleets.models import EveFleet, EveFleetAudience, EveFleetLocation
from fleets.router import fixup_fleet_status, EveFleetTrackingResponse
from fleets.notifications import get_fleet_discord_notification
from fleets.tasks import update_fleet_schedule

BASE_URL = "/api/fleets"

logger = logging.getLogger(__name__)


def disconnect_fleet_signals():
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


def setup_fleet_reference_data():
    """Create reference data needed for fleets"""
    EveFleetAudience.objects.create(
        name="Test Audience",
    )
    EveFleetLocation.objects.create(
        location_id=123,
        location_name="Test Location",
        solar_system_id=234,
        solar_system_name="Somewhere",
    )


def make_test_fleet(
    description: str, fc_user: User, start: datetime.datetime = None
) -> EveFleet:
    if start is None:
        start = datetime.datetime.now() + datetime.timedelta(hours=1)

    return EveFleet.objects.create(
        start_time=start,
        description=description,
        type="training",
        status="pending",
        created_by=fc_user,
        audience=EveFleetAudience.objects.first(),
        location=EveFleetLocation.objects.first(),
    )


class FleetHelperTestCase(SimpleTestCase):
    """Tests for Fleet helper code"""

    def test_discord_notification_template(self):
        notification = get_fleet_discord_notification(
            fleet_id=123,
            fleet_type="training",
            fleet_location="Jita",
            fleet_audience="Alliance",
            fleet_commander_name="Fleet Commander",
            fleet_commander_id=1234,
            fleet_description="Test fleet",
            fleet_voice_channel="Voice 1",
            fleet_voice_channel_link="link",
        )
        self.assertEqual("@everyone", notification["content"])


class FleetRouterTestCase(TestCase):
    """Test cases for the fleet router."""

    def setUp(self):
        # create test client
        self.client = Client()

        disconnect_fleet_signals()

        setup_fleet_reference_data()

        super().setUp()

    def test_get_fleet_v1_v2(self):
        make_test_fleet("Test fleet 1", self.user)

        response = self.client.get(
            f"{BASE_URL}?upcoming=true",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)

        response = self.client.get(
            f"{BASE_URL}/v2?upcoming=true",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)

    def test_get_fleets_v3(self):
        make_test_fleet("Test fleet 1", self.user)
        make_test_fleet("Test fleet 2", self.user)

        response = self.client.get(
            f"{BASE_URL}/v3?fleet_filter=upcoming",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        fleets = response.json()
        # logger.info("fleets v3 response = %s", fleets)
        self.assertEqual(2, len(fleets))

    def test_get_fleet(self):
        fleet = make_test_fleet("Test fleet", self.user)

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

        fleet = make_test_fleet("Test fleet", self.user)

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
        fleet = make_test_fleet("Test", self.user)
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


class FleetTaskTests(TestCase):
    """Tests of the Fleet background tasks."""

    def test_update_fleet_schedule_task(self):
        setup_fleet_reference_data()
        make_test_fleet("Test fleet 1", self.user)

        fc = EveCharacter.objects.create(
            character_id=1234,
            character_name="Mr FC",
            user=self.user,
        )
        EvePrimaryCharacter.objects.create(
            user=self.user,
            character=fc,
        )
        DiscordUser.objects.create(
            id=1,
            discord_tag="MrFC",
            user=self.user,
        )

        with patch("fleets.tasks.discord_client") as discord_mock:
            update_fleet_schedule()

            discord_mock.update_message.assert_called()
            discord_mock.create_message.assert_called()
            discord_mock.delete_message.assert_called()
