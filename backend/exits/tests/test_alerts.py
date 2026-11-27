from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.test import TestCase
from django.utils import timezone

import applications.signals as application_signals
from applications.models import EveCorporationApplication
from discord.models import DiscordChannel, DiscordGuild
from eveonline.models import EveCharacter, EveCorporation
from exits.helpers import alerts
from exits.helpers.answers import answer
from exits.models import Departure, RecruiterAlert

CHANNEL = 4242
# The real one, kept before the class-level patch replaces it.
# pylint: disable-next=protected-access
REAL_ENQUEUE = application_signals._enqueue_after_commit


@patch("applications.signals._enqueue_after_commit")
class RecruiterAlertTest(TestCase):
    def setUp(self):
        self.channel = DiscordChannel.objects.create(
            channel_id=CHANNEL,
            guild=DiscordGuild.objects.get_or_create(
                guild_id=4243, defaults={"name": "Alliance"}
            )[0],
            name="recruiter-alerts",
            channel_type=DiscordChannel.TEXT,
            receive_recruiter_alerts=True,
        )
        self.ceo = User.objects.create(username="old ceo")
        self.old_corp = EveCorporation.objects.create(
            corporation_id=98000001,
            name="Example Corp",
            track_exits=True,
            ceo=EveCharacter.objects.create(
                character_id=2112000001,
                character_name="Arkan Veld",
                user=self.ceo,
            ),
        )
        self.new_corp = EveCorporation.objects.create(
            corporation_id=98000002, name="Other Corp"
        )
        self.third_corp = EveCorporation.objects.create(
            corporation_id=98000003, name="Third Corp"
        )
        self.applicant = User.objects.create(username="applicant")
        EveCharacter.objects.create(
            character_id=31, character_name="Dren Halvik", user=self.applicant
        )
        now = timezone.now()
        self.departure = Departure.objects.create(
            corporation=self.old_corp,
            character_id=31,
            user=self.applicant,
            first_missing_at=now,
            status="confirmed",
            confirmed_at=now,
            kind="exit",
        )
        self.discord = MagicMock()
        self.discord.create_message.return_value.json.return_value = {
            "id": "777"
        }
        patcher = patch.object(alerts, "discord", self.discord)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _apply(self, corporation_id=98000002):
        return EveCorporationApplication.objects.create(
            corporation_id=corporation_id,
            user=self.applicant,
            status="pending",
        )

    def _answer(self, **fields):
        values = {
            "reason": "kicked_other",
            "can_rejoin": True,
            "note": "Secret note",
        }
        values.update(fields)
        with self.captureOnCommitCallbacks(execute=True):
            answer(self.ceo, self.old_corp, [self.departure.pk], **values)

    def _messages(self):
        return [
            c.kwargs["message"]
            for c in self.discord.create_message.call_args_list
        ]

    def test_no_history_no_alert(self, enqueue_mock):
        self.assertFalse(alerts.send_alert(self._apply().pk))
        self.discord.create_message.assert_not_called()

    def test_inactive_kick_no_alert(self, enqueue_mock):
        self._answer(reason="kicked_inactive")
        self.assertFalse(alerts.send_alert(self._apply().pk))
        self.discord.create_message.assert_not_called()

    def test_kicked_other_alerts_once(self, enqueue_mock):
        self._answer()
        application = self._apply()
        self.assertTrue(alerts.send_alert(application.pk))
        self.assertFalse(alerts.send_alert(application.pk))
        self.assertEqual(self.discord.create_message.call_count, 1)
        self.assertEqual(
            self.discord.create_message.call_args.kwargs["channel_id"], CHANNEL
        )
        alert = RecruiterAlert.objects.get()
        self.assertEqual(alert.reason, "kicked_other")
        self.assertEqual(alert.message_id, 777)

    def test_flag_alert_after_kicked_other_alert(self, enqueue_mock):
        self._answer()
        application = self._apply()
        alerts.send_alert(application.pk)
        with patch("exits.tasks.alert_application.delay") as queued:
            self._answer(can_rejoin=False)
        queued.assert_called_once_with(application.pk)
        self.assertTrue(alerts.send_alert(application.pk))
        self.assertIn(
            "can't-rejoin flag from Example Corp", self._messages()[-1]
        )
        self.assertEqual(RecruiterAlert.objects.count(), 2)

    def test_new_flag_alerts_open_applications(self, enqueue_mock):
        open_application = self._apply()
        EveCorporationApplication.objects.create(
            corporation_id=98000003, user=self.applicant, status="rejected"
        )
        with patch("exits.tasks.alert_application.delay") as queued:
            self._answer(can_rejoin=False)
        queued.assert_called_once_with(open_application.pk)

    def test_transfer_alerts_new_corporation(self, enqueue_mock):
        self._answer()
        application = self._apply()
        self.assertTrue(alerts.send_alert(application.pk))
        application.corporation_id = 98000003
        application.save()
        self.assertTrue(alerts.send_alert(application.pk))
        self.assertIn("applying to Third Corp", self._messages()[-1])

    def test_alert_has_no_notes(self, enqueue_mock):
        self._answer(can_rejoin=False)
        alerts.send_alert(self._apply().pk)
        [message] = self._messages()
        self.assertIn(
            "Dren Halvik, applying to Other Corp, has alliance history",
            message,
        )
        self.assertNotIn("Secret note", message)
        self.assertNotIn("Arkan Veld", message)
        self.assertNotIn("kicked", message.lower())
        self.assertIn("/alliance/corporations/application/98000002/", message)

    def test_new_application_queues_the_alert(self, enqueue_mock):
        del enqueue_mock  # replaced below by the real enqueue
        # Other application tests disconnect this receiver and leave it off;
        # connecting with its dispatch_uid is a no-op when it's already on.
        post_save.connect(
            application_signals.eve_corporation_application_post_save,
            sender=EveCorporationApplication,
            dispatch_uid="eve_corporation_application_post_save",
        )
        with patch(
            "applications.signals.alert_application"
        ) as alert_mock, patch(
            "applications.signals.sync_application_thread_task"
        ), patch(
            "applications.signals._enqueue_after_commit", REAL_ENQUEUE
        ):
            with self.captureOnCommitCallbacks(execute=True):
                application = self._apply()
            alert_mock.delay.assert_called_once_with(application.pk)
            alert_mock.delay.reset_mock()
            with self.captureOnCommitCallbacks(execute=True):
                application.description = "edited"
                application.save()
            alert_mock.delay.assert_not_called()

    def test_no_channel_logs_and_sends_nothing(self, enqueue_mock):
        self.channel.receive_recruiter_alerts = False
        self.channel.save()
        self._answer()
        self.assertFalse(alerts.send_alert(self._apply().pk))
        self.discord.create_message.assert_not_called()
        self.assertFalse(RecruiterAlert.objects.exists())

    def test_channel_on_inactive_guild_sends_nothing(self, enqueue_mock):
        self.channel.guild.is_active = False
        self.channel.guild.save()
        self._answer()
        self.assertFalse(alerts.send_alert(self._apply().pk))
        self.discord.create_message.assert_not_called()
