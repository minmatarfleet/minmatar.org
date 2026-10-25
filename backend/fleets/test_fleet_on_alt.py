"""Running a fleet on another of the FC's characters.

docs/fleets/fleet-on-alt.md: the start finds whichever of the FC's
characters is boss (main first), members see the main "in game as" the
alt, and public pages see only the alt.
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import Client

from app.test import TestCase
from eveonline.client import EsiResponse
from eveonline.models import EveCharacter
from users.helpers import add_user_permission

from fleets.helpers.fleet_boss import (
    NO_BOSS,
    alt_for_boss,
    find_fleet_boss,
    in_game_fleet_commander,
)
from fleets.models import EveFleetInstance
from fleets.notifications import get_fleet_discord_notification
from fleets.tests import (
    disconnect_fleet_signals,
    make_test_fleet,
    setup_fc,
    setup_fleet_reference_data,
)

BASE_URL = "/api/fleets"
ALT_ID = 5678
ESI_FLEET_ID = 777001


def _not_in_fleet():
    return EsiResponse(
        response_code=404, data={"error": "Character is not in a fleet"}
    )


def _boss_of(character_id):
    return EsiResponse(
        response_code=200,
        data={
            "fleet_id": ESI_FLEET_ID,
            "fleet_boss_id": character_id,
            "role": "fleet_commander",
        },
    )


def _esi_by_character(responses: dict):
    """An EsiClient class mock answering get_active_fleet per character."""

    def client(character):
        character_id = getattr(character, "character_id", character)
        instance = MagicMock()
        instance.get_active_fleet.return_value = responses.get(
            character_id, _not_in_fleet()
        )
        instance.update_fleet_details.return_value = EsiResponse(
            response_code=204, data={}
        )
        return instance

    return MagicMock(side_effect=client)


class FleetOnAltTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        super().setUp()
        add_user_permission(self.user, "view_evefleet")
        self.main_id = setup_fc(self.user)
        self.alt = EveCharacter.objects.create(
            character_id=ALT_ID, character_name="Henri Gray", user=self.user
        )

    def _patch_esi(self, responses):
        esi = _esi_by_character(responses)
        return patch("fleets.helpers.fleet_boss.EsiClient", esi), patch(
            "fleets.models.EsiClient", esi
        )

    def test_main_first(self):
        boss_patch, models_patch = self._patch_esi(
            {self.main_id: _boss_of(self.main_id), ALT_ID: _boss_of(ALT_ID)}
        )
        with boss_patch, models_patch:
            character, data = find_fleet_boss(self.user, 1)
        self.assertEqual(self.main_id, character.character_id)
        self.assertEqual(ESI_FLEET_ID, data["fleet_id"])

    def test_falls_through_to_the_alt_that_is_boss(self):
        boss_patch, models_patch = self._patch_esi({ALT_ID: _boss_of(ALT_ID)})
        with boss_patch, models_patch:
            character, _ = find_fleet_boss(self.user, 1)
        self.assertEqual(ALT_ID, character.character_id)

    def test_none_is_boss_names_the_characters_checked(self):
        boss_patch, models_patch = self._patch_esi({})
        with boss_patch, models_patch:
            with self.assertRaises(RuntimeError) as raised:
                find_fleet_boss(self.user, 1)
        message = str(raised.exception)
        self.assertIn(NO_BOSS, message)
        self.assertIn("Mr FC", message)
        self.assertIn("Henri Gray", message)

    def test_main_only_keeps_its_own_error(self):
        self.alt.delete()
        boss_patch, models_patch = self._patch_esi({})
        with boss_patch, models_patch:
            with self.assertRaises(RuntimeError) as raised:
                find_fleet_boss(self.user, 1)
        self.assertIn("not in a fleet", str(raised.exception))

    def test_start_tracking_on_the_alt(self):
        fleet = make_test_fleet("Alt fleet", self.user)
        fleet.disable_motd = True
        fleet.save()
        boss_patch, models_patch = self._patch_esi({ALT_ID: _boss_of(ALT_ID)})
        with boss_patch, models_patch, patch("discord.outbox.DiscordClient"):
            response = self.client.post(
                f"{BASE_URL}/{fleet.id}/tracking",
                data=None,
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            )
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            ALT_ID, EveFleetInstance.objects.get(eve_fleet=fleet).boss_id
        )

        detail = self.client.get(
            f"{BASE_URL}/{fleet.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        ).json()
        # The FC stays their main; the alt comes alongside.
        self.assertEqual(self.user.id, detail["fleet_commander"])
        self.assertEqual(ALT_ID, detail["fleet_commander_alt_character_id"])
        self.assertEqual("Henri Gray", detail["fleet_commander_alt_name"])

    def test_start_tracking_none_is_boss(self):
        fleet = make_test_fleet("Alt fleet", self.user)
        boss_patch, models_patch = self._patch_esi({})
        with boss_patch, models_patch:
            response = self.client.post(
                f"{BASE_URL}/{fleet.id}/tracking",
                data=None,
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            )
        self.assertEqual(400, response.status_code)
        self.assertIn(NO_BOSS, response.json()["detail"])

    def test_start_now_on_the_alt(self):
        boss_patch, models_patch = self._patch_esi({ALT_ID: _boss_of(ALT_ID)})
        with boss_patch, models_patch:
            response = self.client.post(
                f"{BASE_URL}/start-now",
                {},
                "application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual("Mr FC", body["fleet_commander_name"])
        self.assertEqual("Henri Gray", body["fleet_commander_alt_name"])

    def test_on_the_main_there_is_no_alt(self):
        fleet = make_test_fleet("Main fleet", self.user)
        EveFleetInstance.objects.create(
            id=ESI_FLEET_ID, eve_fleet=fleet, boss_id=self.main_id
        )
        self.assertIsNone(fleet.fleet_commander_alt)
        self.assertEqual(
            self.main_id, in_game_fleet_commander(fleet).character_id
        )

    def test_boss_passed_to_someone_else_is_not_an_alt(self):
        other = User.objects.create(username="other_fc")
        EveCharacter.objects.create(
            character_id=9999, character_name="Someone", user=other
        )
        fleet = make_test_fleet("Passed fleet", self.user)
        self.assertIsNone(alt_for_boss(fleet, 9999, fleet.fleet_commander))

    def test_motd_and_public_view_name_the_alt(self):
        fleet = make_test_fleet("Alt fleet", self.user)
        instance = EveFleetInstance.objects.create(
            id=ESI_FLEET_ID, eve_fleet=fleet, boss_id=ALT_ID
        )
        self.assertEqual(
            "Henri Gray", fleet.fleet_commander_alt.character_name
        )
        self.assertIn("Henri Gray", instance.build_motd())
        self.assertNotIn("Mr FC", instance.build_motd())

    def test_ping_names_the_in_game_character(self):
        payload = get_fleet_discord_notification(
            fleet_id=1,
            fleet_type="Non-Strategic",
            fleet_location="Amamake",
            fleet_audience="Alliance",
            fleet_commander_name="Mr FC",
            fleet_commander_id=self.main_id,
            fleet_description="Roam",
            fleet_voice_channel=None,
            fleet_voice_channel_link=None,
            fleet_commander_in_game_name="Henri Gray",
        )
        embed = payload["embeds"][0]
        self.assertEqual("Mr FC", embed["author"]["name"])
        self.assertIn("**FC IN GAME**: HENRI GRAY", embed["description"])

    def test_ping_on_the_main_has_no_in_game_line(self):
        payload = get_fleet_discord_notification(
            fleet_id=1,
            fleet_type="Non-Strategic",
            fleet_location="Amamake",
            fleet_audience="Alliance",
            fleet_commander_name="Mr FC",
            fleet_commander_id=self.main_id,
            fleet_description="Roam",
            fleet_voice_channel=None,
            fleet_voice_channel_link=None,
        )
        self.assertNotIn("FC IN GAME", payload["embeds"][0]["description"])
