from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from eveonline.constants import MINMATAR_FLEET_ALLIANCE_ID
from eveonline.models import EveAlliance, EveCharacter, EveCorporation
from exits.helpers.departures import confirm_due, is_npc_corporation
from exits.models import Departure


class ConfirmDueTest(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.fl33t = EveAlliance.objects.create(
            alliance_id=MINMATAR_FLEET_ALLIANCE_ID,
            name="Minmatar Fleet Alliance",
        )
        self.corporation = EveCorporation.objects.create(
            corporation_id=98000001,
            name="Example Corp",
            alliance=self.fl33t,
            track_exits=True,
        )

    def _departure(self, character_id, hours_ago=49):
        return Departure.objects.create(
            corporation=self.corporation,
            character_id=character_id,
            first_missing_at=self.now - timedelta(hours=hours_ago),
        )

    def _character(self, character_id, corporation_id):
        return EveCharacter.objects.create(
            character_id=character_id,
            character_name=f"Pilot {character_id}",
            corporation_id=corporation_id,
        )

    def test_npc_range(self):
        self.assertTrue(is_npc_corporation(1000167))
        self.assertFalse(is_npc_corporation(98000001))
        self.assertFalse(is_npc_corporation(None))

    def test_not_confirmed_before_48_hours(self):
        self._character(1, 1000167)
        departure = self._departure(1, hours_ago=47)
        self.assertEqual(confirm_due(self.now), 0)
        departure.refresh_from_db()
        self.assertEqual(departure.status, "pending")

    def test_npc_destination_is_exit(self):
        self._character(1, 1000167)
        departure = self._departure(1)
        self.assertEqual(confirm_due(self.now), 1)
        departure.refresh_from_db()
        self.assertEqual(departure.status, "confirmed")
        self.assertEqual(departure.confirmed_at, self.now)
        self.assertEqual(departure.kind, "exit")
        self.assertTrue(departure.destination_is_npc)
        self.assertEqual(departure.destination_corporation_id, 1000167)

    def test_alliance_corporation_is_alliance_move(self):
        EveCorporation.objects.create(
            corporation_id=98000002, name="Other Corp", alliance=self.fl33t
        )
        self._character(1, 98000002)
        departure = self._departure(1)
        confirm_due(self.now)
        departure.refresh_from_db()
        self.assertEqual(departure.kind, "alliance_move")
        self.assertFalse(departure.destination_is_npc)

    def test_tracked_non_alliance_corporation_is_alliance_move(self):
        EveCorporation.objects.create(
            corporation_id=98000003, name="Mining Corp", track_exits=True
        )
        self._character(1, 98000003)
        departure = self._departure(1)
        confirm_due(self.now)
        departure.refresh_from_db()
        self.assertEqual(departure.kind, "alliance_move")

    def test_back_in_corporation_is_dropped(self):
        self._character(1, self.corporation.corporation_id)
        departure = self._departure(1)
        self.assertEqual(confirm_due(self.now), 0)
        departure.refresh_from_db()
        self.assertEqual(departure.status, "dropped")

    def test_unknown_character_is_exit_without_destination(self):
        departure = self._departure(1)
        confirm_due(self.now)
        departure.refresh_from_db()
        self.assertEqual(departure.status, "confirmed")
        self.assertEqual(departure.kind, "exit")
        self.assertIsNone(departure.destination_corporation_id)
