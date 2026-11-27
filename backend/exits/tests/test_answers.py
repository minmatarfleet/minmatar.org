from datetime import timedelta
from unittest.mock import MagicMock

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from eveonline.models import EveCharacter, EveCorporation
from exits.admin import RejoinFlagAdmin
from exits.helpers.answers import AnswerError, answer, clear_flag
from exits.helpers.grouping import group
from exits.models import Departure, RejoinFlag


class AnswerTest(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.ceo = User.objects.create(username="ceo")
        ceo_character = EveCharacter.objects.create(
            character_id=2112000001, character_name="Ceo", user=self.ceo
        )
        self.director = User.objects.create(username="director")
        self.corporation = EveCorporation.objects.create(
            corporation_id=98000001,
            name="Example Corp",
            track_exits=True,
            ceo=ceo_character,
        )
        self.other = EveCorporation.objects.create(
            corporation_id=98000002, name="Other Corp", track_exits=True
        )

    def _confirmed(
        self, character_id, corporation=None, user=None, hours_ago=50
    ):
        return Departure.objects.create(
            corporation=corporation or self.corporation,
            character_id=character_id,
            user=user,
            first_missing_at=self.now - timedelta(hours=hours_ago),
            status="confirmed",
            confirmed_at=self.now,
            kind="exit",
        )

    def _answer(self, departures, by=None, **fields):
        values = {"reason": "kicked_inactive", "can_rejoin": True, "note": ""}
        values.update(fields)
        return answer(
            by or self.ceo,
            self.corporation,
            [d.pk for d in departures],
            **values,
        )

    def test_bulk_answer_sets_every_row(self):
        rows = [self._confirmed(1), self._confirmed(2), self._confirmed(3)]
        self._answer(rows)
        for row in rows:
            row.refresh_from_db()
            self.assertEqual(row.reason, "kicked_inactive")
            self.assertIs(row.can_rejoin, True)
            self.assertEqual(row.answered_by, self.ceo)
            self.assertIsNotNone(row.answered_at)

    def test_kick_needs_can_rejoin(self):
        with self.assertRaises(AnswerError) as caught:
            self._answer([self._confirmed(1)], can_rejoin=None)
        self.assertEqual(caught.exception.status_code, 400)

    def test_cant_rejoin_needs_note(self):
        with self.assertRaises(AnswerError):
            self._answer(
                [self._confirmed(1)],
                reason="kicked_other",
                can_rejoin=False,
                note=" ",
            )

    def test_unknown_reason_is_refused(self):
        with self.assertRaises(AnswerError):
            self._answer([self._confirmed(1)], reason="bored")

    def test_cant_rejoin_creates_flag(self):
        departure = self._confirmed(1)
        for _ in range(2):
            self._answer(
                [departure],
                reason="kicked_other",
                can_rejoin=False,
                note="Awoxed",
            )
        flag = RejoinFlag.objects.get()
        self.assertEqual(flag.character_id, 1)
        self.assertEqual(flag.corporation, self.corporation)
        self.assertEqual(flag.note, "Awoxed")
        self.assertEqual(flag.set_by, self.ceo)
        self.assertIsNone(flag.cleared_at)

    def test_rejoin_true_clears_flag(self):
        departure = self._confirmed(1)
        self._answer(
            [departure], reason="kicked_other", can_rejoin=False, note="x"
        )
        self._answer([departure], reason="kicked_other", can_rejoin=True)
        flag = RejoinFlag.objects.get()
        self.assertIsNotNone(flag.cleared_at)
        self.assertEqual(flag.cleared_by, self.ceo)

    def test_left_sets_survey_due_in_an_hour(self):
        departure = self._confirmed(1)
        self._answer([departure], reason="left", can_rejoin=False)
        departure.refresh_from_db()
        self.assertIsNone(departure.can_rejoin)
        self.assertAlmostEqual(
            departure.survey_due_at,
            timezone.now() + timedelta(hours=1),
            delta=timedelta(minutes=1),
        )
        self.assertFalse(RejoinFlag.objects.exists())
        self._answer([departure], reason="kicked_inactive", can_rejoin=True)
        departure.refresh_from_db()
        self.assertIsNone(departure.survey_due_at)

    def test_director_is_refused(self):
        with self.assertRaises(AnswerError) as caught:
            self._answer([self._confirmed(1)], by=self.director)
        self.assertEqual(caught.exception.status_code, 403)

    def test_other_corporations_rows_refused(self):
        theirs = self._confirmed(1, corporation=self.other)
        with self.assertRaises(AnswerError) as caught:
            self._answer([theirs])
        self.assertEqual(caught.exception.status_code, 404)
        theirs.refresh_from_db()
        self.assertEqual(theirs.reason, "")

    def test_pending_rows_refused(self):
        pending = Departure.objects.create(
            corporation=self.corporation,
            character_id=9,
            first_missing_at=self.now,
        )
        with self.assertRaises(AnswerError):
            self._answer([pending])

    def test_alts_group_together(self):
        account = User.objects.create(username="alts")
        main = self._confirmed(1, user=account, hours_ago=50)
        alt = self._confirmed(2, user=account, hours_ago=60)
        later = self._confirmed(3, user=account, hours_ago=120)
        loner = self._confirmed(4, hours_ago=55)
        groups = group([main, alt, later, loner])
        self.assertEqual(
            [[d.character_id for d in g] for g in groups], [[1, 2], [4], [3]]
        )

    def test_clear_flag_by_new_ceo(self):
        departure = self._confirmed(1)
        self._answer(
            [departure], reason="kicked_other", can_rejoin=False, note="x"
        )
        flag = RejoinFlag.objects.get()
        new_ceo = User.objects.create(username="new ceo")
        self.corporation.ceo = EveCharacter.objects.create(
            character_id=2112000005, character_name="New Ceo", user=new_ceo
        )
        self.corporation.save()
        with self.assertRaises(AnswerError):
            clear_flag(self.ceo, flag)
        clear_flag(new_ceo, flag)
        flag.refresh_from_db()
        self.assertEqual(flag.cleared_by, new_ceo)

    def test_admin_clear_action_records_who(self):
        departure = self._confirmed(1)
        self._answer(
            [departure], reason="kicked_other", can_rejoin=False, note="x"
        )
        admin_user = User.objects.create(username="admin", is_superuser=True)
        request = MagicMock(user=admin_user)
        model_admin = RejoinFlagAdmin(RejoinFlag, AdminSite())
        model_admin.message_user = MagicMock()
        model_admin.clear_flags(request, RejoinFlag.objects.all())
        flag = RejoinFlag.objects.get()
        self.assertEqual(flag.cleared_by, admin_user)
        self.assertIsNotNone(flag.cleared_at)
