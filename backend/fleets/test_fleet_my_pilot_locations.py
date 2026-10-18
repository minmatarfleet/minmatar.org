"""Form-up card: where the caller's characters are, from ESI."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client
from eveuniverse.models import EveConstellation, EveRegion, EveSolarSystem

from app.test import TestCase
from app.testing import make_token
from eveonline.client import (
    ERROR_CALLING_ESI,
    NO_VALID_ESI_TOKEN,
    SUCCESS,
    EsiResponse,
)
from eveonline.models import EveCharacter
from fleets.tests import (
    BASE_URL,
    disconnect_fleet_signals,
    make_test_fleet,
    setup_fleet_reference_data,
)
from users.helpers import add_user_permission

DOCKED = 1001
NO_SCOPE = 1002
ESI_DOWN = 1003
IN_SPACE = 1004
AMAMAKE = 30002537


def _seed_amamake():
    region, _ = EveRegion.objects.get_or_create(
        id=10000042, defaults={"name": "Metropolis"}
    )
    constellation, _ = EveConstellation.objects.get_or_create(
        id=20000372,
        defaults={
            "name": "Hed",
            "eve_region": region,
            "position_x": 0.0,
            "position_y": 0.0,
            "position_z": 0.0,
        },
    )
    EveSolarSystem.objects.create(
        id=AMAMAKE,
        name="Amamake",
        eve_constellation=constellation,
        security_status=0.4,
        position_x=0.0,
        position_y=0.0,
        position_z=0.0,
        enabled_sections=0,
    )


LOCATIONS = {
    DOCKED: EsiResponse(
        SUCCESS, data={"solar_system_id": AMAMAKE, "station_id": 60005686}
    ),
    NO_SCOPE: EsiResponse(NO_VALID_ESI_TOKEN),
    ESI_DOWN: EsiResponse(502),
    IN_SPACE: EsiResponse(SUCCESS, data={"solar_system_id": AMAMAKE}),
}


class FakeEsiClient:
    calls = []

    def __init__(self, character):
        self.character_id = character.character_id

    def get_character_location(self):
        FakeEsiClient.calls.append(self.character_id)
        return LOCATIONS[self.character_id]


@patch("fleets.helpers.pilot_locations.EsiClient", FakeEsiClient)
class FleetMyPilotLocationsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        FakeEsiClient.calls = []
        self.client = Client()
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        _seed_amamake()
        add_user_permission(self.user, "view_evefleet")
        for character_id, name in (
            (DOCKED, "A Docked"),
            (NO_SCOPE, "B No Scope"),
            (ESI_DOWN, "C Esi Down"),
            (IN_SPACE, "D In Space"),
        ):
            EveCharacter.objects.create(
                character_id=character_id,
                character_name=name,
                user=self.user,
            )
        other = User.objects.create(username="other")
        EveCharacter.objects.create(
            character_id=5001, character_name="Not Mine", user=other
        )
        self.fleet = make_test_fleet(
            "Fleet", User.objects.create(username="fc")
        )

    def _get(self, user=None):
        token = make_token(user) if user else self.token
        return self.client.get(
            f"{BASE_URL}/{self.fleet.id}/my-pilot-locations",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    def _rows(self):
        response = self._get()
        self.assertEqual(200, response.status_code, response.content)
        return {row["character_id"]: row for row in response.json()}

    def test_scope_present(self):
        rows = self._rows()

        self.assertEqual(
            {
                "character_id": DOCKED,
                "character_name": "A Docked",
                "solar_system_id": AMAMAKE,
                "solar_system_name": "Amamake",
                "station_id": 60005686,
                "structure_id": None,
                "has_location_scope": True,
            },
            rows[DOCKED],
        )
        self.assertIsNone(rows[IN_SPACE]["station_id"])
        self.assertEqual("Amamake", rows[IN_SPACE]["solar_system_name"])
        self.assertNotIn(5001, rows)

    def test_scope_missing(self):
        row = self._rows()[NO_SCOPE]

        self.assertFalse(row["has_location_scope"])
        self.assertIsNone(row["solar_system_id"])
        self.assertIsNone(row["solar_system_name"])

    def test_esi_error_for_one_character(self):
        rows = self._rows()

        self.assertEqual(4, len(rows))
        self.assertTrue(rows[ESI_DOWN]["has_location_scope"])
        self.assertIsNone(rows[ESI_DOWN]["solar_system_id"])
        self.assertEqual(AMAMAKE, rows[DOCKED]["solar_system_id"])

    def test_locations_are_cached_but_errors_are_not(self):
        self._rows()
        self._rows()

        self.assertEqual(1, FakeEsiClient.calls.count(DOCKED))
        self.assertEqual(1, FakeEsiClient.calls.count(NO_SCOPE))
        self.assertEqual(2, FakeEsiClient.calls.count(ESI_DOWN))

    def test_viewer_must_see_the_fleet(self):
        outsider = User.objects.create(username="outsider")
        self.assertEqual(403, self._get(outsider).status_code)
        self.assertEqual([], FakeEsiClient.calls)


class EsiClientLocationTestCase(TestCase):
    def test_reads_the_location_route_with_the_location_scope(self):
        # pylint: disable=import-outside-toplevel
        from eveonline.client import EsiClient

        with patch.object(
            EsiClient, "_raw_get", return_value=EsiResponse(ERROR_CALLING_ESI)
        ) as raw_get:
            EsiClient(DOCKED).get_character_location()

        raw_get.assert_called_once_with(
            f"/characters/{DOCKED}/location/",
            ["esi-location.read_location.v1"],
        )
