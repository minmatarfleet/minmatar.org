from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from discord.models import DiscordUser
from eveonline.models import EveCharacter, EveCorporation, EvePlayer
from exits.helpers.answers import AnswerError, answer
from exits.models import Departure
from notifications.channels import ChannelSendError, EveMailRefused
from surveys.helpers import exit_tokens
from surveys.helpers.exit_sending import send_due
from surveys.models import ExitSurveyInvite

SENDING = "surveys.helpers.exit_sending"


class ExitSendingTest(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.ceo = User.objects.create(username="ceo")
        self.corporation = EveCorporation.objects.create(
            corporation_id=98000001,
            name="Example Corp",
            track_exits=True,
            ceo=EveCharacter.objects.create(
                character_id=2112000001,
                character_name="Arkan Veld",
                user=self.ceo,
            ),
        )
        EveCorporation.objects.create(
            corporation_id=98000002, name="Tribal Liberation Force"
        )
        mail = patch(f"{SENDING}.send_eve_mail_to_character")
        self.mail = mail.start()
        self.addCleanup(mail.stop)
        dm = patch(f"{SENDING}._send_discord")
        self.dm = dm.start()
        self.addCleanup(dm.stop)

    def _left(
        self,
        character_id,
        user=None,
        kind="exit",
        destination=1000167,
        hours_ago=50,
    ):
        departure = Departure.objects.create(
            corporation=self.corporation,
            character_id=character_id,
            user=user,
            first_missing_at=self.now - timedelta(hours=hours_ago),
            status="confirmed",
            confirmed_at=self.now - timedelta(hours=2),
            kind=kind,
            destination_corporation_id=destination,
        )
        answer(
            self.ceo,
            self.corporation,
            [departure.pk],
            reason="left",
            can_rejoin=None,
            note="",
        )
        departure.refresh_from_db()
        return departure

    def _due(self, *departures):
        Departure.objects.filter(pk__in=[d.pk for d in departures]).update(
            survey_due_at=self.now - timedelta(minutes=1)
        )

    def _pilot(self, name, character_id, discord=False):
        user = User.objects.create(username=name)
        character = EveCharacter.objects.create(
            character_id=character_id, character_name=name, user=user
        )
        EvePlayer.objects.create(
            user=user, primary_character=character, nickname=name
        )
        if discord:
            DiscordUser.objects.create(
                id=character_id, discord_tag=name, user=user
            )
        return user

    def test_not_sent_within_the_hour(self):
        self._left(31)
        self.assertEqual(send_due(self.now), 0)
        self.mail.assert_not_called()

    def test_changed_answer_within_hour_sends_nothing(self):
        departure = self._left(31)
        answer(
            self.ceo,
            self.corporation,
            [departure.pk],
            reason="kicked_inactive",
            can_rejoin=True,
            note="",
        )
        self.assertEqual(send_due(self.now + timedelta(hours=2)), 0)
        self.mail.assert_not_called()

    def test_exit_gets_exit_survey(self):
        departure = self._left(31)
        self._due(departure)
        self.assertEqual(send_due(self.now), 1)
        invite = ExitSurveyInvite.objects.get()
        self.assertEqual(invite.definition_key, "exit")
        self.assertEqual(invite.channel, "eve_mail")
        self.assertEqual(invite.status, "sent")
        self.assertEqual(
            invite.expires_at, invite.sent_at + timedelta(days=30)
        )
        character_id, subject, body = self.mail.call_args.args
        self.assertEqual(character_id, 31)
        self.assertEqual(subject, "You left Example Corp. How was it?")
        self.assertIn("/exit-survey/", body)
        self.assertIn("only I read the answers", body)

    def test_alliance_move_gets_move_survey(self):
        departure = self._left(31, kind="alliance_move", destination=98000002)
        self._due(departure)
        send_due(self.now)
        self.assertEqual(
            ExitSurveyInvite.objects.get().definition_key, "alliance_move"
        )

    def test_one_survey_per_account(self):
        user = self._pilot("Kesh Varo", 41)
        EveCharacter.objects.create(
            character_id=42, character_name="Kesh Alt", user=user
        )
        first = self._left(41, user=user)
        self._due(first)
        send_due(self.now)
        later = self._left(42, user=user, hours_ago=300)
        self._due(later)
        self.assertEqual(send_due(self.now), 0)
        self.assertEqual(ExitSurveyInvite.objects.count(), 1)
        later.refresh_from_db()
        self.assertIsNone(later.survey_due_at)

    def test_alts_that_left_together_get_one_survey_to_the_main(self):
        user = self._pilot("Toren Ashblade", 51)
        EveCharacter.objects.create(
            character_id=52, character_name="Toren Alt", user=user
        )
        alt = self._left(52, user=user, hours_ago=51)
        main = self._left(51, user=user, hours_ago=50)
        self._due(alt, main)
        self.assertEqual(send_due(self.now), 1)
        self.assertEqual(self.mail.call_args.args[0], 51)

    def test_unregistered_character_gets_mail(self):
        departure = self._left(61)
        self._due(departure)
        send_due(self.now)
        self.assertEqual(self.mail.call_args.args[0], 61)
        self.assertIsNone(ExitSurveyInvite.objects.get().user)

    def test_unknown_destination_gets_no_survey(self):
        departure = self._left(62, destination=None)
        self._due(departure)
        self.assertEqual(send_due(self.now), 0)
        self.assertFalse(ExitSurveyInvite.objects.exists())

    def test_cspa_falls_back_to_discord(self):
        user = self._pilot("Lyss Corran", 71, discord=True)
        departure = self._left(71, user=user)
        self._due(departure)
        self.mail.side_effect = EveMailRefused("refused")
        send_due(self.now)
        invite = ExitSurveyInvite.objects.get()
        self.assertEqual(invite.channel, "discord_dm")
        self.assertEqual(invite.status, "sent")
        self.assertEqual(self.dm.call_args.args[0], user)

    def test_no_discord_marks_not_delivered(self):
        departure = self._left(81)
        self._due(departure)
        self.mail.side_effect = EveMailRefused("refused")
        send_due(self.now)
        invite = ExitSurveyInvite.objects.get()
        self.assertEqual(invite.status, "not_delivered")
        self.assertEqual(invite.channel, "")
        self.dm.assert_not_called()

    def test_permanent_mail_failure_is_not_retried(self):
        departure = self._left(82)
        self._due(departure)
        self.mail.side_effect = ChannelSendError("404", retryable=False)
        send_due(self.now)
        invite = ExitSurveyInvite.objects.get()
        self.assertEqual(invite.status, "not_delivered")
        self.assertEqual(invite.channel, "")
        departure.refresh_from_db()
        self.assertIsNone(departure.survey_due_at)
        self.assertEqual(send_due(self.now + timedelta(minutes=15)), 0)
        self.assertEqual(self.mail.call_count, 1)

    def test_retryable_mail_failure_is_retried(self):
        departure = self._left(83)
        self._due(departure)
        self.mail.side_effect = ChannelSendError("timeout", retryable=True)
        self.assertEqual(send_due(self.now), 0)
        self.assertFalse(ExitSurveyInvite.objects.exists())
        departure.refresh_from_db()
        self.assertIsNotNone(departure.survey_due_at)
        self.mail.side_effect = None
        self.assertEqual(send_due(self.now + timedelta(minutes=15)), 1)
        self.assertEqual(ExitSurveyInvite.objects.get().status, "sent")

    def test_permanent_discord_failure_after_cspa_is_not_retried(self):
        user = self._pilot("Tarn Esk", 84, discord=True)
        departure = self._left(84, user=user)
        self._due(departure)
        self.mail.side_effect = EveMailRefused("refused")
        self.dm.side_effect = ChannelSendError("403", retryable=False)
        send_due(self.now)
        invite = ExitSurveyInvite.objects.get()
        self.assertEqual(invite.status, "not_delivered")
        self.assertEqual(invite.channel, "")
        departure.refresh_from_db()
        self.assertIsNone(departure.survey_due_at)
        self.assertEqual(send_due(self.now + timedelta(minutes=15)), 0)
        self.assertEqual(self.mail.call_count, 1)
        self.assertEqual(self.dm.call_count, 1)

    def test_reason_locked_after_invite(self):
        departure = self._left(91)
        self._due(departure)
        send_due(self.now)
        with self.assertRaises(AnswerError) as caught:
            answer(
                self.ceo,
                self.corporation,
                [departure.pk],
                reason="kicked_other",
                can_rejoin=False,
                note="x",
            )
        self.assertEqual(caught.exception.status_code, 409)
        # The note can still change.
        answer(
            self.ceo,
            self.corporation,
            [departure.pk],
            reason="left",
            can_rejoin=None,
            note="Moved to nullsec",
        )

    def test_token_expires_after_30_days(self):
        departure = self._left(95)
        self._due(departure)
        send_due(self.now)
        invite = ExitSurveyInvite.objects.get()
        token = exit_tokens.mint(invite)
        self.assertEqual(exit_tokens.invite_for(token), invite)
        with patch(
            "django.core.signing.time.time",
            return_value=self.now.timestamp() + 31 * 86400,
        ):
            with self.assertRaises(exit_tokens.TokenGone):
                exit_tokens.invite_for(token)
        with self.assertRaises(exit_tokens.TokenInvalid):
            exit_tokens.invite_for("not-a-token")

    def test_used_token_is_gone(self):
        departure = self._left(96)
        self._due(departure)
        send_due(self.now)
        invite = ExitSurveyInvite.objects.get()
        invite.responded_at = self.now
        invite.save()
        with self.assertRaises(exit_tokens.TokenGone):
            exit_tokens.invite_for(exit_tokens.mint(invite))
