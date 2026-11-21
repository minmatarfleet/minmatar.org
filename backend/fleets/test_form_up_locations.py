"""Fleet form-up while deployed: quick start at a picked location, the
flash form's default location, and the locations list."""

from unittest.mock import patch

from django.core.cache import cache
from django.test import Client

from app.test import TestCase
from eveonline.client import SUCCESS, EsiResponse
from eveonline.models import EveCharacter, EveLocation
from fleets.models import EveFleet, EveFleetInstance
from fleets.tests import (
    BASE_URL,
    disconnect_fleet_signals,
    patch_fleet_esi,
    setup_fc,
    setup_fleet_reference_data,
)

HOME = 123
FORWARD = 777
ALT_ID = 4321


class FakeLocationClient:
    """ESI location per character id; anything else is in space."""

    docked: dict = {}

    def __init__(self, character):
        self.character_id = character.character_id

    def get_character_location(self):
        station = FakeLocationClient.docked.get(self.character_id)
        data = {"solar_system_id": 30000142}
        if station:
            data["structure_id"] = station
        return EsiResponse(SUCCESS, data=data)


class FormUpTestBase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.client = Client()
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        self.forward = EveLocation.objects.create(
            location_id=FORWARD,
            location_name="Forward System - Forward Station",
            solar_system_id=778,
            solar_system_name="Forward System",
            short_name="Forward Station",
            fleets_active=True,
            deployment_active=True,
        )

    def get(self, path):
        return self.client.get(
            f"{BASE_URL}{path}", HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )


class LocationListTests(FormUpTestBase):
    def test_locations_say_which_is_a_deployment(self):
        setup_fc(self.user)
        response = self.get("/v2/locations")
        self.assertEqual(200, response.status_code, response.content)
        rows = {row["location_id"]: row for row in response.json()}
        self.assertTrue(rows[FORWARD]["deployment_active"])
        self.assertFalse(rows[HOME]["deployment_active"])
        self.assertTrue(rows[HOME]["staging_active"])

    def test_default_needs_fleets_create(self):
        response = self.get("/v2/locations/default")
        self.assertEqual(403, response.status_code)


@patch("fleets.helpers.pilot_locations.EsiClient", FakeLocationClient)
class DefaultLocationTests(FormUpTestBase):
    def setUp(self):
        super().setUp()
        self.main_id = setup_fc(self.user)
        EveCharacter.objects.create(
            character_id=ALT_ID, character_name="Alt", user=self.user
        )
        FakeLocationClient.docked = {}

    def default(self):
        response = self.get("/v2/locations/default")
        self.assertEqual(200, response.status_code, response.content)
        return response.json()["location_id"]

    def test_staging_when_nobody_is_docked_at_a_form_up(self):
        self.assertEqual(HOME, self.default())

    def test_where_the_main_is_docked(self):
        FakeLocationClient.docked = {self.main_id: FORWARD}
        self.assertEqual(FORWARD, self.default())

    def test_where_an_alt_is_docked(self):
        FakeLocationClient.docked = {ALT_ID: FORWARD}
        self.assertEqual(FORWARD, self.default())

    def test_main_wins_over_an_alt(self):
        FakeLocationClient.docked = {self.main_id: HOME, ALT_ID: FORWARD}
        self.assertEqual(HOME, self.default())

    def test_docked_somewhere_else_is_the_staging(self):
        FakeLocationClient.docked = {self.main_id: 999}
        self.assertEqual(HOME, self.default())


class StartNowLocationTests(FormUpTestBase):
    def start(self, esi_mock, body):
        char_id = setup_fc(self.user)
        esi = esi_mock.return_value
        esi.get_active_fleet.return_value = EsiResponse(
            response_code=200,
            data={
                "fleet_id": 555666,
                "fleet_boss_id": char_id,
                "role": "fleet_commander",
            },
        )
        esi.update_fleet_details.return_value = EsiResponse(
            response_code=204, data={}
        )
        return self.client.post(
            f"{BASE_URL}/start-now",
            body,
            "application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

    @patch("discord.outbox.DiscordClient")
    @patch_fleet_esi
    def test_defaults_to_the_staging(self, discord_mock, esi_mock):
        response = self.start(esi_mock, {})
        self.assertEqual(200, response.status_code, response.content)
        fleet = EveFleet.objects.get(id=response.json()["id"])
        self.assertEqual(HOME, fleet.location_id)

    @patch("discord.outbox.DiscordClient")
    @patch_fleet_esi
    def test_forms_up_at_the_picked_location(self, discord_mock, esi_mock):
        response = self.start(esi_mock, {"location_id": FORWARD})
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(
            "Forward System - Forward Station", response.json()["location"]
        )
        fleet = EveFleet.objects.get(id=response.json()["id"])
        self.assertEqual(FORWARD, fleet.location_id)
        motd = EveFleetInstance.objects.get(id=555666).build_motd()
        self.assertIn("Forward Station", motd)
        self.assertIn(str(FORWARD), motd)

    @patch("discord.outbox.DiscordClient")
    @patch_fleet_esi
    def test_rejects_a_location_that_is_not_a_form_up(
        self, discord_mock, esi_mock
    ):
        EveLocation.objects.filter(location_id=FORWARD).update(
            fleets_active=False
        )
        before = EveFleet.objects.count()
        response = self.start(esi_mock, {"location_id": FORWARD})
        self.assertEqual(400, response.status_code)
        self.assertEqual(before, EveFleet.objects.count())
