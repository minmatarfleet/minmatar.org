import datetime
import logging
from unittest.mock import patch, MagicMock, ANY

from django.db.models import signals
from django.test import Client, SimpleTestCase
from django.contrib.auth.models import User, Permission

from app.test import TestCase
from eveonline.client import EsiResponse
from eveonline.models import EveCharacter, EveCorporation
from eveonline.helpers.characters import set_primary_character
from discord.models import DiscordUser
from fleets.models import (
    EveFleet,
    EveFleetAudience,
    EveFleetLocation,
    EveFleetInstance,
    EveFleetInstanceMember,
)
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
        discord_channel_name="TestChannel",
    )
    EveFleetLocation.objects.create(
        location_id=123,
        location_name="Test Location",
        solar_system_id=234,
        solar_system_name="Somewhere",
    )


def setup_fc(user):
    character_id = 1234

    user.user_permissions.add(Permission.objects.get(codename="add_evefleet"))
    corp = EveCorporation.objects.create(corporation_id=1, name="Test Corp")
    character = EveCharacter.objects.create(
        character_id=character_id,
        character_name="Mr FC",
        user=user,
        corporation=corp,
    )
    set_primary_character(user, character)

    DiscordUser.objects.create(
        id=1,
        discord_tag="MrFC",
        user=user,
    )

    return character_id


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

    def test_get_fleet_reference_data(self):
        setup_fc(self.user)

        response = self.client.get(
            f"{BASE_URL}/types",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)

        response = self.client.get(
            f"{BASE_URL}/v2/locations",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)

        response = self.client.get(
            f"{BASE_URL}/audiences",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)

    def test_create_fleet_endpoint(self):
        setup_fc(self.user)

        data = {
            "type": "training",
            "description": "Test fleet",
            "start_time": datetime.datetime.now(),
            "audience_id": EveFleetAudience.objects.first().id,
            "location_id": EveFleetLocation.objects.first().location_id,
        }

        response = self.client.post(
            f"{BASE_URL}",
            data,
            "application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        fleet_response = response.json()
        self.assertTrue(fleet_response["id"])

        db_fleet = EveFleet.objects.filter(id=fleet_response["id"]).first()
        self.assertIsNotNone(db_fleet)

    @patch("fleets.models.EsiClient")
    @patch("fleets.models.discord")
    def test_start_fleet_endpoint(self, discord_mock, esi_mock):
        char_id = setup_fc(self.user)
        fleet = make_test_fleet("Test", self.user)
        fleet.disable_motd = True
        fleet.save()

        esi_mock_instance = esi_mock.return_value
        esi_mock_instance.get_active_fleet.return_value = EsiResponse(
            response_code=200,
            data={
                "fleet_id": fleet.id,
                "fleet_boss_id": char_id,
            },
        )
        response = self.client.post(
            f"{BASE_URL}/{fleet.id}/tracking",
            data=None,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)

    @patch("fleets.models.EsiClient")
    @patch("fleets.models.discord")
    def test_start_fleet_with_char(self, discord_mock, esi_mock):
        fc_id = setup_fc(self.user)
        fleet = make_test_fleet("Test", self.user)
        fleet.disable_motd = True
        fleet.save()

        esi_mock_instance = esi_mock.return_value
        esi_mock_instance.get_active_fleet.return_value = EsiResponse(
            response_code=200,
            data={
                "fleet_id": fleet.id,
                "fleet_boss_id": fc_id,
            },
        )
        data = {
            "fc_character_id": fc_id,
        }
        response = self.client.post(
            f"{BASE_URL}/{fleet.id}/tracking",
            data,
            "application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)

    def add_fleet_member(
        self,
        instance: EveFleetInstance,
        char_id: int,
    ):
        EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance,
            character_id=char_id,
            character_name=f"Pilot {char_id}",
            ship_type_id=1,
            solar_system_id=1,
            squad_id=1,
            wing_id=1,
            join_time=datetime.datetime.now(),
        )

    def test_fleet_metrics(self):
        self.make_superuser()
        setup_fc(self.user)

        fleet = make_test_fleet("Test", self.user)
        fleet.start_time = datetime.datetime(2025, 1, 1, 21, 30, 0)
        fleet.save()
        instance = EveFleetInstance.objects.create(id=1, eve_fleet=fleet)
        self.add_fleet_member(instance, 1)
        self.add_fleet_member(instance, 2)

        response = self.client.get(
            f"{BASE_URL}/metrics",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        metrics = response.json()
        self.assertEqual(
            metrics,
            [
                {
                    "fleet_id": fleet.id,
                    "members": 2,
                    "time_region": "EU_US",
                    "location_name": "Test Location",
                    "status": "pending",
                    "fc_corp_name": "Test Corp",
                    "audience_name": "Test Audience",
                },
            ],
        )

    @patch("fleets.router.DiscordClient")
    def test_fleet_preping(self, discord_mock):
        mock_client = MagicMock()
        discord_mock.return_value = mock_client
        self.make_superuser()
        setup_fc(self.user)
        fleet = make_test_fleet("Test", self.user)
        response = self.client.post(
            f"{BASE_URL}/{fleet.id}/preping",
            "",
            "application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(202, response.status_code)

        mock_client.create_message.assert_called_with(
            channel_id=ANY, payload=ANY
        )

    @patch("fleets.router.EsiClient")
    def test_user_active_fleets(self, esi_client_class):
        esi_mock = esi_client_class.return_value

        esi_mock.get_active_fleet.return_value = EsiResponse(
            response_code=200,
            data={
                "fleet_id": 123456,
                "fleet_boss_id": 23456,
                "role": "squad_member",
            },
        )

        self.make_superuser()
        setup_fc(self.user)

        response = self.client.get(
            f"{BASE_URL}/current",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        fleets = response.json()
        self.assertEqual(1, len(fleets))
        self.assertEqual("squad_member", fleets[0]["fleet_role"])


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
        set_primary_character(self.user, fc)

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

    @patch("fleets.models.EsiClient")
    @patch("fleets.models.discord")
    def test_fleet_member_update(self, discord, esi):
        esi_mock = esi.return_value

        fc_id = setup_fc(self.user)
        fleet = make_test_fleet("Test", self.user)
        fleet.disable_motd = True
        fleet.status = "active"
        fleet.save()

        efi = EveFleetInstance.objects.create(
            id=1234,
            eve_fleet=fleet,
        )

        esi_mock.get_active_fleet.return_value = EsiResponse(
            response_code=200,
            data={
                "fleet_id": fleet.id,
                "fleet_boss_id": fc_id,
            },
        )
        fleet_member_response = EsiResponse(
            response_code=200,
            data=[
                {
                    "character_id": fc_id,
                    "join_time": datetime.datetime.now(),
                    "role": "squad_member",
                    "role_name": "squad_member",
                    "ship_type_id": 1000,
                    "squad_id": 10,
                    "wing_id": 20,
                    "solar_system_id": 3001,
                    "station_id": 4001,
                    "takes_fleet_warp": True,
                }
            ],
        )
        esi_mock.get_fleet_members.return_value = fleet_member_response
        esi_mock.resolve_universe_names.return_value = EsiResponse(
            response_code=200,
            data=[
                {"id": fc_id, "name": "Mr FC"},
                {"id": 1000, "name": "X-Wing"},
                {"id": 3001, "name": "Homesystem"},
                {"id": 4001, "name": "Homestation"},
            ],
        )

        efi.update_fleet_members()

        self.assertEqual("active", efi.eve_fleet.status)

        efi.boss_id = fc_id
        efi.save()

        efi.update_fleet_members()

        self.assertEqual("active", efi.eve_fleet.status)

        esi_mock.get_fleet_members.return_value = EsiResponse(
            response_code=400,
            response="Mock error",
        )

        efi.update_fleet_members()

        self.assertEqual("active", efi.eve_fleet.status)

        esi_mock.get_active_fleet.return_value = EsiResponse(
            response_code=400,
        )

        efi.update_fleet_members()

        self.assertEqual("complete", efi.eve_fleet.status)
        self.assertIsNotNone(efi.end_time)
