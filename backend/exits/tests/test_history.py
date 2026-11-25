from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from eveonline.models import EveCharacter, EveCorporation
from exits.helpers.answers import answer
from exits.helpers.history import (
    active_flags_for,
    character_ids_for,
    history_for,
)
from exits.models import Departure


class HistoryTest(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.ceo = User.objects.create(username="ceo")
        ceo_character = EveCharacter.objects.create(
            character_id=2112000001, character_name="Arkan Veld", user=self.ceo
        )
        self.corporation = EveCorporation.objects.create(
            corporation_id=98000001,
            name="Example Corp",
            track_exits=True,
            ceo=ceo_character,
        )
        self.pilot = User.objects.create(username="pilot")
        EveCharacter.objects.create(
            character_id=11, character_name="Main", user=self.pilot
        )
        EveCharacter.objects.create(
            character_id=12, character_name="Alt", user=self.pilot
        )

    def _departure(self, character_id, user=None, hours_ago=50):
        return Departure.objects.create(
            corporation=self.corporation,
            character_id=character_id,
            user=user,
            first_missing_at=self.now - timedelta(hours=hours_ago),
            status="confirmed",
            confirmed_at=self.now,
            kind="exit",
        )

    def _answer(self, departure, **fields):
        values = {
            "reason": "kicked_other",
            "can_rejoin": False,
            "note": "Awoxed",
        }
        values.update(fields)
        answer(self.ceo, self.corporation, [departure.pk], **values)

    def test_character_ids_cover_the_account(self):
        self.assertEqual(character_ids_for(self.pilot, [99]), {11, 12, 99})
        self.assertEqual(character_ids_for(None, [99]), {99})

    def test_history_covers_the_account(self):
        # The alt left before it was linked to the account: matched by character.
        self._answer(self._departure(12))
        [entry] = history_for(self.pilot, [11])
        self.assertEqual(entry.corporation_name, "Example Corp")
        self.assertEqual(entry.reason, "kicked_other")
        self.assertEqual(entry.note, "Awoxed")
        self.assertEqual(entry.answered_by_name, "Arkan Veld")
        self.assertTrue(entry.flag_active)

    def test_unanswered_departures_left_out(self):
        self._departure(11, user=self.pilot)
        self.assertEqual(history_for(self.pilot, [11]), [])

    def test_alt_group_is_one_entry(self):
        main = self._departure(11, user=self.pilot)
        alt = self._departure(12, user=self.pilot, hours_ago=52)
        answer(
            self.ceo,
            self.corporation,
            [main.pk, alt.pk],
            reason="kicked_inactive",
            can_rejoin=True,
            note="",
        )
        self.assertEqual(len(history_for(self.pilot, [11])), 1)

    def test_cleared_flag_is_not_active(self):
        departure = self._departure(11, user=self.pilot)
        self._answer(departure)
        self.assertEqual(len(active_flags_for(self.pilot, [11])), 1)
        self._answer(departure, can_rejoin=True)
        self.assertEqual(active_flags_for(self.pilot, [11]), [])
        [entry] = history_for(self.pilot, [11])
        self.assertFalse(entry.flag_active)
