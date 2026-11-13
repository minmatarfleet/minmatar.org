"""Fleet invite feedback: who is asked, what the form stores, and the send.

See docs/fleets/private-fleets.md.
"""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.db.models import signals
from django.test import Client
from django.utils import timezone

from app.test import TestCase
from app.testing import auth_headers
from discord.models import DiscordUser
from eveonline.models import EveLocation
from fleets.helpers.invite_feedback import PROBE_KEY, _dm_context, run_action
from fleets.models import (
    EveFleet,
    EveFleetAudience,
    EveFleetInvite,
    EveFleetInviteWave,
    FleetInviteFeedback,
    FleetInviteFeedbackRound,
)
from fleets.signals import (
    private_fleet_thread_on_save,
    update_fleet_schedule_on_save,
)
from fleets.tests import setup_fleet_reference_data
from notifications.models import (
    NotificationChannel,
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationPreference,
)
from notifications.discord_format import discord_embed_from_payload
from notifications.types.fleets import render_fleet_invite_feedback
from tribes.tests.publishing_fixtures import make_user

SECRET = "SECRET DROP"


def setUpModule():
    signals.post_save.disconnect(
        sender=EveFleet, dispatch_uid="update_fleet_schedule_on_save"
    )
    signals.post_save.disconnect(
        sender=EveFleet, dispatch_uid="private_fleet_thread_on_save"
    )


def tearDownModule():
    signals.post_save.connect(
        update_fleet_schedule_on_save,
        sender=EveFleet,
        dispatch_uid="update_fleet_schedule_on_save",
    )
    signals.post_save.connect(
        private_fleet_thread_on_save,
        sender=EveFleet,
        dispatch_uid="private_fleet_thread_on_save",
    )


@patch("notifications.service.deliver_notification.apply_async")
@patch("notifications.service.deliver_notification.delay")
class InviteFeedbackTests(TestCase):
    def setUp(self):
        super().setUp()
        setup_fleet_reference_data()
        self.audience = EveFleetAudience.objects.get(name="Test Audience")
        self.location = EveLocation.objects.get(location_id=123)
        self.fc = make_user("stratfc", perms=("manage_any_fleet",))
        self.fc.user_permissions.add(
            Permission.objects.get(codename="view_evefleet")
        )
        DiscordUser.objects.create(
            id=4242, discord_tag="stratfc", user=self.fc
        )
        self.client = Client()

    def fleet(self, *, days_ago=2, status="complete", **fields):
        values = {
            "type": "non_strategic",
            "objective": "Sunday roam",
            "start_time": timezone.now() - timedelta(days=days_ago),
            "created_by": self.fc,
            "audience": self.audience,
            "location": self.location,
            "status": status,
            "invite_only": False,
        }
        values.update(fields)
        return EveFleet.objects.create(**values)

    def invite(self, fleet, user, **fields):
        wave, unused_created = EveFleetInviteWave.objects.get_or_create(
            eve_fleet=fleet,
            number=1,
            defaults={"sent_by": self.fc},
        )
        values = {
            "eve_fleet": fleet,
            "wave": wave,
            "user": user,
            "answer": EveFleetInvite.ANSWER_PENDING,
            "dm_delivered": True,
            "sent_at": fleet.start_time,
            "source_kind": "pilot",
        }
        values.update(fields)
        return EveFleetInvite.objects.create(**values)

    def opt_out(self, user, type_key="fleets.invite"):
        NotificationPreference.objects.create(
            user=user,
            notification_type=type_key,
            channel=NotificationChannel.DISCORD,
            enabled=False,
        )

    def send(self):
        return run_action("send", confirm=True)

    def test_cohort_keeps_past_untracked_and_drops_the_rest(
        self, unused_delay, unused_async
    ):
        pilot = make_user("pilot")
        kept = self.invite(
            self.fleet(status="unknown", objective="Armor brawl"), pilot
        )
        self.invite(
            self.fleet(days_ago=-1, status="pending", objective="Future"),
            pilot,
        )
        self.invite(
            self.fleet(status="cancelled", objective="Cancelled roam"),
            pilot,
        )
        self.invite(
            self.fleet(objective="Undelivered"),
            pilot,
            dm_delivered=False,
        )
        opted = make_user("opted")
        self.opt_out(opted)
        self.invite(self.fleet(objective="Opted out"), opted)
        text = run_action("preview", confirm=False)
        self.assertIn("Nothing is sent", text)
        self.assertIn("1 pilot.", text)
        self.assertIn("1 not started", text)
        self.assertIn("1 cancelled", text)
        self.assertIn("1 undelivered", text)
        self.assertIn("1 opted out", text)
        self.assertEqual(FleetInviteFeedbackRound.objects.count(), 0)
        self.send()
        row = FleetInviteFeedback.objects.get(user=pilot)
        self.assertEqual(len(row.invites), 1)
        self.assertEqual(row.invites[0]["fleet_id"], kept.eve_fleet_id)
        self.assertFalse(
            FleetInviteFeedback.objects.filter(user=opted).exists()
        )

    def test_snapshot_lists_every_invite_newest_first(
        self, unused_delay, unused_async
    ):
        pilot = make_user("pilot")
        older = self.invite(
            self.fleet(days_ago=5, objective="Armor brawl"),
            pilot,
            answer=EveFleetInvite.ANSWER_IN,
        )
        newer = self.invite(
            self.fleet(days_ago=1, objective="Sunday roam"),
            pilot,
            answer=EveFleetInvite.ANSWER_PENDING,
        )
        private = self.invite(
            self.fleet(
                days_ago=3,
                objective=SECRET,
                invite_only=True,
                description="do not leak",
            ),
            pilot,
            answer=EveFleetInvite.ANSWER_OUT,
            source_kind="first_week",
            first_viewed_at=timezone.now(),
        )
        self.send()
        row = FleetInviteFeedback.objects.get(user=pilot)
        self.assertEqual(
            [item["fleet_id"] for item in row.invites],
            [newer.eve_fleet_id, private.eve_fleet_id, older.eve_fleet_id],
        )
        stored = next(
            item
            for item in row.invites
            if item["fleet_id"] == private.eve_fleet_id
        )
        self.assertEqual(stored["title"], "")
        self.assertTrue(stored["private"])
        self.assertNotIn(SECRET, str(row.invites))
        response = self.client.get(
            "/api/fleets/invite-feedback", **auth_headers(pilot)
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["intro"], "")
        self.assertEqual(
            [row["title"] for row in body["invites"]],
            ["Sunday roam", "Private fleet", "Armor brawl"],
        )
        self.assertEqual(
            [row["answer_label"] for row in body["invites"]],
            ["No answer", "Sitting out", "In"],
        )
        self.assertEqual(
            [row["title"] for row in body["pending_invites"]],
            ["Sunday roam"],
        )
        keys = [question["key"] for question in body["questions"]]
        self.assertEqual(keys, ["felt", "sitting_out", "why", "improve"])
        self.assertNotIn(SECRET, response.content.decode())

    def test_answered_form_has_no_open_question(
        self, unused_delay, unused_async
    ):
        pilot = make_user("pilot")
        self.invite(
            self.fleet(),
            pilot,
            answer=EveFleetInvite.ANSWER_OUT,
        )
        self.send()
        response = self.client.get(
            "/api/fleets/invite-feedback", **auth_headers(pilot)
        )
        keys = [question["key"] for question in response.json()["questions"]]
        self.assertEqual(keys, ["felt", "sitting_out", "improve"])
        self.assertEqual(response.json()["pending_invites"], [])

    def test_validation(self, unused_delay, unused_async):
        pilot = make_user("pilot")
        self.invite(self.fleet(), pilot)
        self.send()
        url = "/api/fleets/invite-feedback"
        missing = self.client.post(
            url,
            data={"felt": "", "improve": ["fewer"]},
            content_type="application/json",
            **auth_headers(pilot),
        )
        self.assertEqual(missing.status_code, 400)
        self.assertIn(
            "Pick how these invites felt most of the time.",
            missing.json()["errors"],
        )
        self.assertIn(
            "Pick what was most often going on.", missing.json()["errors"]
        )
        other = self.client.post(
            url,
            data={
                "felt": "fine",
                "sitting_out": "normal",
                "why": "other",
                "why_text": "",
                "improve": ["fewer"],
            },
            content_type="application/json",
            **auth_headers(pilot),
        )
        self.assertEqual(other.status_code, 400)
        self.assertIn("Say what the other reason was.", other.json()["errors"])
        mixed = self.client.post(
            url,
            data={
                "felt": "fine",
                "sitting_out": "normal",
                "why": "silence",
                "improve": ["nothing", "fewer"],
            },
            content_type="application/json",
            **auth_headers(pilot),
        )
        self.assertEqual(mixed.status_code, 400)
        self.assertIn(
            '"Nothing. They were fine" stands on its own.',
            mixed.json()["errors"],
        )
        long = self.client.post(
            url,
            data={
                "felt": "fine",
                "sitting_out": "normal",
                "why": "silence",
                "improve": ["fewer"],
                "comment": "x" * 281,
            },
            content_type="application/json",
            **auth_headers(pilot),
        )
        self.assertEqual(long.status_code, 400)
        self.assertIn("Keep the comment to a sentence.", long.json()["errors"])
        saved = self.client.post(
            url,
            data={
                "felt": "fine",
                "sitting_out": "letdown",
                "why": "silence",
                "improve": ["lighter"],
                "comment": "Tell me the doctrine in the DM.",
            },
            content_type="application/json",
            **auth_headers(pilot),
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["state"], "thanks")
        self.assertEqual(
            saved.json()["detail"],
            "You can change your answers until the survey closes.",
        )
        self.assertNotIn("your name", saved.json()["detail"].lower())
        self.assertIn(
            "Sitting out is only not this fleet", saved.json()["body"]
        )
        again = self.client.get(url, **auth_headers(pilot))
        self.assertEqual(again.json()["state"], "thanks")
        editing = self.client.get(url + "?edit=true", **auth_headers(pilot))
        self.assertEqual(editing.json()["state"], "form")
        self.assertEqual(editing.json()["answers"]["felt"], "fine")

    def test_why_rejected_when_every_invite_was_answered(
        self, unused_delay, unused_async
    ):
        pilot = make_user("pilot")
        self.invite(self.fleet(), pilot, answer=EveFleetInvite.ANSWER_IN)
        self.send()
        response = self.client.post(
            "/api/fleets/invite-feedback",
            data={
                "felt": "glad",
                "sitting_out": "normal",
                "why": "later",
                "improve": ["nothing"],
            },
            content_type="application/json",
            **auth_headers(pilot),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("doesn't apply", response.json()["detail"])
        row = FleetInviteFeedback.objects.get(user=pilot)
        self.assertIsNone(row.submitted_at)

    def test_stranger_and_closed(self, unused_delay, unused_async):
        pilot = make_user("pilot")
        stranger = make_user("stranger")
        self.invite(self.fleet(), pilot, answer=EveFleetInvite.ANSWER_IN)
        self.send()
        stranger_response = self.client.get(
            "/api/fleets/invite-feedback", **auth_headers(stranger)
        )
        self.assertEqual(stranger_response.status_code, 200)
        self.assertEqual(stranger_response.json()["state"], "not_invited")
        run_action("close", confirm=True)
        closed = self.client.get(
            "/api/fleets/invite-feedback", **auth_headers(pilot)
        )
        self.assertEqual(closed.json()["state"], "closed")
        self.assertEqual(closed.json()["heading"], "This survey is closed.")
        posted = self.client.post(
            "/api/fleets/invite-feedback",
            data={
                "felt": "fine",
                "sitting_out": "normal",
                "improve": ["nothing"],
            },
            content_type="application/json",
            **auth_headers(pilot),
        )
        self.assertEqual(posted.json()["state"], "closed")
        self.assertIsNone(
            FleetInviteFeedback.objects.get(user=pilot).submitted_at
        )

    def test_second_send_does_not_add_pilots_or_another_dm(
        self, unused_delay, unused_async
    ):
        first = make_user("first")
        quiet = make_user("quiet")
        self.invite(self.fleet(objective="One"), first)
        self.invite(self.fleet(objective="Two"), quiet)
        self.opt_out(quiet, "fleets.invite_feedback")
        message = self.send()
        self.assertIn("Sent to 1 pilot", message)
        self.assertEqual(FleetInviteFeedbackRound.objects.count(), 1)
        self.assertIsNotNone(
            FleetInviteFeedback.objects.get(user=first).sent_at
        )
        self.assertIsNone(FleetInviteFeedback.objects.get(user=quiet).sent_at)
        self.assertEqual(NotificationDelivery.objects.count(), 1)
        later = make_user("later")
        self.invite(self.fleet(objective="After"), later)
        again = self.send()
        self.assertIn("No new pilots were added", again)
        self.assertIn("No new DM went out", again)
        self.assertFalse(
            FleetInviteFeedback.objects.filter(user=later).exists()
        )
        self.assertEqual(FleetInviteFeedbackRound.objects.count(), 1)
        self.assertEqual(
            NotificationDelivery.objects.filter(user=first).count(), 1
        )
        self.assertEqual(
            NotificationDelivery.objects.filter(user=quiet).count(), 0
        )

    def test_remind_skips(self, unused_delay, unused_async):
        due = make_user("due")
        failed = make_user("failed")
        opted = make_user("optedlater")
        done = make_user("done")
        for user in (due, failed, opted, done):
            self.invite(self.fleet(), user, answer=EveFleetInvite.ANSWER_IN)
        self.send()
        old = timezone.now() - timedelta(days=4)
        FleetInviteFeedback.objects.update(sent_at=old)
        for row in FleetInviteFeedback.objects.all():
            NotificationDelivery.objects.filter(user=row.user).update(
                status=NotificationDeliveryStatus.SENT
            )
        failed_row = FleetInviteFeedback.objects.get(user=failed)
        NotificationDelivery.objects.filter(user=failed).update(
            status=NotificationDeliveryStatus.FAILED
        )
        self.opt_out(opted)
        done_row = FleetInviteFeedback.objects.get(user=done)
        done_row.submitted_at = timezone.now()
        done_row.save(update_fields=["submitted_at"])
        self.assertIsNotNone(failed_row.id)
        message = run_action("remind", confirm=True)
        self.assertIn("Reminded 1 pilot", message)
        self.assertIn("whose first DM didn't send", message)
        self.assertIn("turned fleet invites off", message)
        self.assertIn("already answered", message)
        self.assertIsNotNone(
            FleetInviteFeedback.objects.get(user=due).reminded_at
        )
        second = run_action("remind", confirm=True)
        self.assertIn("Reminded 0 pilots", second)
        self.assertIn("already reminded", second)

    def test_dm_asks_for_two_minutes(self, unused_delay, unused_async):
        payload = render_fleet_invite_feedback(_dm_context(reminder=False))
        self.assertEqual(payload["title"], "We need your feedback")
        embed = discord_embed_from_payload({**payload, "feature": "fleets"})
        self.assertEqual(embed["title"], "We need your feedback")
        self.assertEqual(
            payload["discord_message"],
            (
                "Hey! You've been invited to a few fleets lately- could "
                "you take two minutes to share some feedback on the "
                "process?"
            ),
        )
        button = payload["discord_components"][0]["components"][0]
        self.assertEqual(button["label"], "Provide feedback")

    def test_dry_run_command_writes_nothing(self, unused_delay, unused_async):
        pilot = make_user("pilot")
        self.invite(self.fleet(), pilot)
        out = StringIO()
        call_command("send_fleet_invite_feedback", "--dry-run", stdout=out)
        self.assertIn("Nothing is sent", out.getvalue())
        self.assertEqual(FleetInviteFeedbackRound.objects.count(), 0)
        self.assertEqual(NotificationDelivery.objects.count(), 0)

    def test_one_pilot_send_does_not_open_the_real_round(
        self, unused_delay, unused_async
    ):
        bear = make_user("BearThatCares")
        other = make_user("other")
        self.invite(self.fleet(), bear)
        self.invite(self.fleet(), other)
        out = StringIO()
        call_command(
            "send_fleet_invite_feedback", "--user", "bearthatcares", stdout=out
        )
        self.assertIn("Sent the form to BearThatCares.", out.getvalue())
        probe = FleetInviteFeedbackRound.objects.get()
        self.assertEqual(probe.key, PROBE_KEY)
        self.assertEqual(
            list(probe.responses.values_list("user", flat=True)), [bear.id]
        )
        results = self.client.get(
            "/api/fleets/invite-feedback/results?link=true",
            **auth_headers(self.fc),
        )
        self.assertFalse(results.json()["show_link"])
        self.send()
        official = FleetInviteFeedbackRound.objects.exclude(
            key=PROBE_KEY
        ).get()
        self.assertEqual(
            set(official.responses.values_list("user_id", flat=True)),
            {bear.id, other.id},
        )

    def test_discord_command_is_strategic_only(
        self, unused_delay, unused_async
    ):
        pilot = make_user("pilot")
        self.invite(self.fleet(), pilot)
        denied = self.client.post(
            "/api/fleets/invite-feedback/command",
            data={
                "discord_user_id": 4242,
                "action": "send",
                "confirm": True,
            },
            content_type="application/json",
            **auth_headers(pilot),
        )
        self.assertEqual(denied.status_code, 403)
        preview = self.client.post(
            "/api/fleets/invite-feedback/command",
            data={"discord_user_id": 4242, "action": "preview"},
            content_type="application/json",
            **auth_headers(self.fc),
        )
        self.assertEqual(preview.status_code, 200)
        self.assertIn("Nothing is sent", preview.json()["message"])
        self.assertEqual(FleetInviteFeedbackRound.objects.count(), 0)
        blocked = self.client.post(
            "/api/fleets/invite-feedback/command",
            data={
                "discord_user_id": 4242,
                "action": "send",
                "confirm": True,
            },
            content_type="application/json",
            **auth_headers(self.fc),
        )
        self.assertEqual(blocked.status_code, 400)
        self.assertIn("production command", blocked.json()["detail"])
        self.assertEqual(FleetInviteFeedbackRound.objects.count(), 0)
        unknown = self.client.post(
            "/api/fleets/invite-feedback/command",
            data={"discord_user_id": 4242, "action": "nope"},
            content_type="application/json",
            **auth_headers(self.fc),
        )
        self.assertEqual(unknown.status_code, 400)

    def test_results_frame_splits_and_privacy(
        self, unused_delay, unused_async
    ):
        opens = [make_user(f"open{index}") for index in range(6)]
        manys = [make_user(f"many{index}") for index in range(6)]
        twos = [make_user(f"two{index}") for index in range(2)]
        privs = [make_user(f"priv{index}") for index in range(2)]
        words = make_user("words")
        for user in opens:
            self.invite(self.fleet(), user)
        for user in [*manys, *twos]:
            count = 3 if user in manys else 2
            for index in range(count):
                self.invite(
                    self.fleet(days_ago=index + 1),
                    user,
                    answer=EveFleetInvite.ANSWER_OUT,
                )
        for user in privs:
            self.invite(
                self.fleet(objective=SECRET, invite_only=True),
                user,
                answer=EveFleetInvite.ANSWER_IN,
            )
        self.invite(self.fleet(), words)
        self.send()

        def submit(user, felt, sitting="normal", pending=False, comment=""):
            posted = self.client.post(
                "/api/fleets/invite-feedback",
                data={
                    "felt": felt,
                    "sitting_out": sitting,
                    "why": "silence" if pending else "",
                    "improve": ["fewer"],
                    "comment": comment,
                },
                content_type="application/json",
                **auth_headers(user),
            )
            self.assertEqual(posted.status_code, 200, posted.content)

        for user in opens:
            submit(user, "much", sitting="letdown", pending=True)
        for user in manys:
            submit(user, "glad")
        for user in twos:
            submit(user, "fine")
        submit(words, "fine", pending=True, comment="the dm was fine")
        denied = self.client.get(
            "/api/fleets/invite-feedback/results",
            **auth_headers(make_user("nope")),
        )
        self.assertEqual(denied.status_code, 403)
        response = self.client.get(
            "/api/fleets/invite-feedback/results", **auth_headers(self.fc)
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertNotIn("user_id", _keys(body))
        self.assertNotIn("fleet_id", _keys(body))
        self.assertNotIn(SECRET, response.content.decode())
        self.assertNotIn("words", response.content.decode())
        self.assertIn("the dm was fine", body["quotes"])
        frame = {row["key"]: row for row in body["frame"]}
        self.assertGreater(frame["open"]["asked_count"], 0)
        self.assertGreater(frame["dose"]["asked_count"], 0)
        dose = {side["key"]: side for side in body["felt_split"]}
        self.assertIn("one", dose)
        self.assertIn("many", dose)
        self.assertIn("2 invites", body["felt_help"])
        chips = {chip["key"] for chip in body["chips"]}
        self.assertIn("all", chips)
        self.assertNotIn("private", chips)
        narrow = self.client.get(
            "/api/fleets/invite-feedback/results?cut=open",
            **auth_headers(self.fc),
        )
        sides = {side["key"] for side in narrow.json()["sitting_out_split"]}
        self.assertNotIn("answered", sides)

    def test_link_flag_does_not_include_quotes(
        self, unused_delay, unused_async
    ):
        pilot = make_user("pilot")
        self.invite(self.fleet(), pilot, answer=EveFleetInvite.ANSWER_IN)
        self.send()
        FleetInviteFeedback.objects.filter(user=pilot).update(
            submitted_at=timezone.now(),
            answers={"comment": "hidden quote", "felt": "fine"},
        )
        response = self.client.get(
            "/api/fleets/invite-feedback/results?link=true",
            **auth_headers(self.fc),
        )
        self.assertTrue(response.json()["show_link"])
        self.assertEqual(response.json()["quotes"], [])


def _keys(payload, found=None):
    found = found if found is not None else set()
    if isinstance(payload, dict):
        found.update(payload)
        for value in payload.values():
            _keys(value, found)
    elif isinstance(payload, list):
        for value in payload:
            _keys(value, found)
    return found
