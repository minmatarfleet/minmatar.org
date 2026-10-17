"""POST /characters/{id}/waypoint: the desktop app's Set destination."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client

from app.test import TestCase
from eveonline.client import NO_VALID_ESI_TOKEN, SUCCESS, EsiResponse
from eveonline.models import EveCharacter

URL = "/api/eveonline/characters/{}/waypoint"
AMAMAKE = 30002537
SET_WAYPOINT = "eveonline.client.EsiClient.set_autopilot_waypoint"


class CharacterWaypointTestCase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.client = Client()
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}
        EveCharacter.objects.create(
            character_id=1001, character_name="Kesra Lund", user=self.user
        )
        EveCharacter.objects.create(
            character_id=2002,
            character_name="Someone Else",
            user=User.objects.create(username="other"),
        )

    def _post(self, character_id, destination_id=AMAMAKE):
        return self.client.post(
            URL.format(character_id),
            {"destination_id": destination_id},
            content_type="application/json",
            **self.auth,
        )

    def test_sets_the_destination_on_your_own_character(self):
        with patch(SET_WAYPOINT, return_value=EsiResponse(SUCCESS)) as call:
            response = self._post(1001)

        self.assertEqual(204, response.status_code, response.content)
        call.assert_called_once_with(AMAMAKE, True)

    def test_never_on_someone_elses_character(self):
        with patch(SET_WAYPOINT) as call:
            response = self._post(2002)

        self.assertEqual(404, response.status_code)
        call.assert_not_called()

    def test_only_systems_and_stations(self):
        with patch(SET_WAYPOINT) as call:
            response = self._post(1001, destination_id=1_000_000_000_000)

        self.assertEqual(400, response.status_code)
        call.assert_not_called()

    def test_without_the_desktop_scopes_says_how_to_fix_it(self):
        with patch(SET_WAYPOINT, return_value=EsiResponse(NO_VALID_ESI_TOKEN)):
            response = self._post(1001)

        self.assertEqual(409, response.status_code)
        self.assertIn("Desktop scopes", response.json()["detail"])
        self.assertIn("Kesra Lund", response.json()["detail"])

    def test_a_stuck_button_is_throttled(self):
        with patch(SET_WAYPOINT, return_value=EsiResponse(SUCCESS)):
            codes = [self._post(1001).status_code for _ in range(21)]

        self.assertEqual([204] * 20 + [429], codes)
