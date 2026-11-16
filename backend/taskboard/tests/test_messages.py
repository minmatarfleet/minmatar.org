import json
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from app.test import TestCase
from app.testing import auth_headers
from eveonline.models import EveCharacter, EvePlayer
from groups.models import UserCommunityStatus
from notifications.models import (
    NotificationChannel,
    NotificationDelivery,
    NotificationPreference,
)
from notifications.types.tasks import (
    TASKS_ASSIGNED_KEY,
    TASKS_REMINDER_KEY,
    TASKS_WEEKLY_KEY,
    render_weekly,
)
from taskboard import messages
from taskboard.models import (
    Task,
    TaskDigestSettings,
    TaskMessageHold,
    TaskPreferences,
)
from taskboard.services import TaskError
from tribes.models import Tribe, TribeGroup, TribeGroupMembership

# A Sunday, 17:00 EVE: the default send time.
SUNDAY_17 = datetime(2026, 11, 22, 17, 0, tzinfo=dt_timezone.utc)


def make_pilot(name: str, character_id: int) -> User:
    user = User.objects.create(username=name)
    character = EveCharacter.objects.create(
        character_id=character_id, character_name=name, user=user
    )
    EvePlayer.objects.create(
        user=user, primary_character=character, nickname=name
    )
    return user


def open_task(user, days_old: int = 5, now=None, **fields) -> Task:
    # Days before the weekly send by default; pass now for the real clock.
    opened = (now or SUNDAY_17) - timedelta(days=days_old)
    values = {
        "kind": Task.KIND_AUTOMATIC,
        "rule": "reauth_character",
        "source_key": f"character:{user.pk}:{days_old}",
        "title": f"Re-add {user.username}",
        "user": user,
        "opened_at": opened,
        "last_activity_at": opened,
    }
    values.update(fields)
    return Task.objects.create(**values)


def say_yes(user, key=TASKS_WEEKLY_KEY):
    messages.set_discord(user, key, True)


def deliveries(user, key):
    return NotificationDelivery.objects.filter(
        user=user, notification_type=key
    )


class WeeklyListTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.pilot = make_pilot("Teysha", 9001)

    def test_only_pilots_who_said_yes_get_it(self):
        open_task(self.pilot)
        messages.send_weekly_lists(now=SUNDAY_17)
        self.assertFalse(deliveries(self.pilot, TASKS_WEEKLY_KEY).exists())
        say_yes(self.pilot)
        messages.send_weekly_lists(now=SUNDAY_17)
        delivery = deliveries(self.pilot, TASKS_WEEKLY_KEY).get()
        self.assertEqual(delivery.channel, NotificationChannel.DISCORD)
        self.assertIn("Re-add Teysha", delivery.payload["discord_message"])

    def test_nothing_waiting_means_no_message(self):
        say_yes(self.pilot)
        # A day-old task isn't in the list yet.
        open_task(self.pilot, days_old=1)
        messages.send_weekly_lists(now=SUNDAY_17)
        self.assertFalse(deliveries(self.pilot, TASKS_WEEKLY_KEY).exists())

    def test_snoozed_suggestions_and_paused_are_left_out(self):
        say_yes(self.pilot)
        open_task(
            self.pilot,
            snoozed_until=SUNDAY_17 + timedelta(days=3),
        )
        open_task(self.pilot, days_old=6, weight="suggestion")
        messages.send_weekly_lists(now=SUNDAY_17)
        self.assertFalse(deliveries(self.pilot, TASKS_WEEKLY_KEY).exists())
        open_task(self.pilot, days_old=7)
        UserCommunityStatus.objects.bulk_create(
            [
                UserCommunityStatus(
                    user=self.pilot,
                    status=UserCommunityStatus.STATUS_ON_LEAVE,
                )
            ]
        )
        messages.send_weekly_lists(now=SUNDAY_17)
        self.assertFalse(deliveries(self.pilot, TASKS_WEEKLY_KEY).exists())

    def test_once_a_week_and_only_at_the_send_time(self):
        say_yes(self.pilot)
        open_task(self.pilot)
        result = messages.send_weekly_lists(now=SUNDAY_17 - timedelta(hours=1))
        self.assertEqual(result["sent"], 0)
        messages.send_weekly_lists(now=SUNDAY_17)
        messages.send_weekly_lists(now=SUNDAY_17 + timedelta(minutes=30))
        self.assertEqual(deliveries(self.pilot, TASKS_WEEKLY_KEY).count(), 1)

    def test_turned_off(self):
        say_yes(self.pilot)
        open_task(self.pilot)
        settings = TaskDigestSettings.load()
        settings.enabled = False
        settings.save()
        messages.send_weekly_lists(now=SUNDAY_17)
        self.assertFalse(deliveries(self.pilot, TASKS_WEEKLY_KEY).exists())

    def test_stats(self):
        say_yes(self.pilot)
        open_task(self.pilot)
        messages.send_weekly_lists(now=SUNDAY_17)
        stats = messages.weekly_stats(now=SUNDAY_17 + timedelta(hours=2))
        self.assertEqual(stats["opted_in"], 1)
        self.assertEqual(stats["had_waiting"], 1)
        self.assertEqual(stats["last_sent_at"], SUNDAY_17)

    def test_render(self):
        payload = render_weekly(
            {"name": "Teysha", "lines": ["**A** · waiting 3 days"]}
        )
        self.assertEqual(payload["title"], "You have 1 thing waiting, Teysha.")
        self.assertEqual(
            payload["discord_components"][0]["components"][0]["label"],
            "Open my tasks",
        )


class QuietHoursTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.pilot = make_pilot("Teysha", 9001)

    def test_window(self):
        prefs = TaskPreferences(quiet_start=22, quiet_end=8)

        def at(hour):
            return SUNDAY_17.replace(hour=hour)

        self.assertTrue(messages.in_quiet_hours(prefs, at(23)))
        self.assertTrue(messages.in_quiet_hours(prefs, at(3)))
        self.assertFalse(messages.in_quiet_hours(prefs, at(8)))
        self.assertFalse(messages.in_quiet_hours(prefs, at(17)))
        self.assertFalse(messages.in_quiet_hours(None, at(23)))

    def test_held_then_sent_together(self):
        TaskPreferences.objects.create(
            user=self.pilot, quiet_start=0, quiet_end=23
        )
        say_yes(self.pilot, TASKS_REMINDER_KEY)
        with patch.object(
            timezone, "now", return_value=SUNDAY_17.replace(hour=5)
        ):
            sent = messages.send_task_message(
                self.pilot, TASKS_REMINDER_KEY, {"leader": "X", "title": "Y"}
            )
        self.assertFalse(sent)
        self.assertEqual(TaskMessageHold.objects.count(), 1)
        self.assertFalse(deliveries(self.pilot, TASKS_REMINDER_KEY).exists())
        # Still quiet: nothing goes out.
        messages.flush_holds(now=SUNDAY_17.replace(hour=10))
        self.assertEqual(TaskMessageHold.objects.count(), 1)
        messages.flush_holds(now=SUNDAY_17.replace(hour=23))
        self.assertEqual(TaskMessageHold.objects.count(), 0)
        self.assertTrue(deliveries(self.pilot, TASKS_REMINDER_KEY).exists())


class RemindTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.pilot = make_pilot("Teysha", 9001)
        self.chief = make_pilot("Casper", 9002)
        tribe = Tribe.objects.create(name="Capitals", chief=self.chief)
        self.group = TribeGroup.objects.create(
            tribe=tribe, name="Dreads", chief=self.chief
        )
        TribeGroupMembership.objects.create(
            user=self.pilot, tribe_group=self.group, status="active"
        )
        say_yes(self.pilot, TASKS_REMINDER_KEY)

    def remind_url(self, task):
        return (
            f"/api/tasks/teams/tribe_group/{self.group.pk}/rules/"
            f"reauth_character/remind/{task.pk}"
        )

    def test_only_after_it_has_waited_and_only_once(self):
        fresh = open_task(self.pilot, days_old=3, now=timezone.now())
        with self.assertRaises(TaskError):
            messages.remind(self.chief, fresh)
        old = open_task(self.pilot, days_old=15, now=timezone.now())
        messages.remind(self.chief, old)
        self.assertEqual(old.reminded_by, self.chief)
        delivery = deliveries(self.pilot, TASKS_REMINDER_KEY).get()
        self.assertIn("Re-add Teysha", delivery.payload["discord_message"])
        with self.assertRaises(TaskError) as raised:
            messages.remind(self.chief, old)
        self.assertEqual(raised.exception.status_code, 409)

    def test_pilots_who_never_opted_in_cannot_be_reminded(self):
        NotificationPreference.objects.filter(user=self.pilot).delete()
        task = open_task(self.pilot, days_old=15, now=timezone.now())
        listing = self.client.get(
            f"/api/tasks/teams/tribe_group/{self.group.pk}/rules/"
            "reauth_character",
            **auth_headers(self.chief),
        ).json()
        self.assertFalse(listing[0]["can_remind"])
        self.assertTrue(listing[0]["reminders_off"])
        with self.assertRaises(TaskError):
            messages.remind(self.chief, task)

    def test_the_pilots_own_chief_can_remind_from_the_team_view(self):
        task = open_task(self.pilot, days_old=15, now=timezone.now())
        stranger = make_pilot("Stranger", 9003)
        response = self.client.post(
            self.remind_url(task), **auth_headers(stranger)
        )
        self.assertEqual(response.status_code, 404)
        listing = self.client.get(
            f"/api/tasks/teams/tribe_group/{self.group.pk}/rules/"
            "reauth_character",
            **auth_headers(self.chief),
        ).json()
        self.assertTrue(listing[0]["can_remind"])
        response = self.client.post(
            self.remind_url(task), **auth_headers(self.chief)
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()[0]["can_remind"])
        self.assertIsNotNone(response.json()[0]["reminded_at"])


class AssignedAndPreferencesTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.root = User.objects.create_superuser("root", "r@x", "pw")
        self.pilot = make_pilot("Teysha", 9001)

    def post_task(self):
        return self.client.post(
            "/api/tasks",
            data=json.dumps(
                {"title": "Write it", "assignee_id": self.pilot.pk}
            ),
            content_type="application/json",
            **auth_headers(self.root),
        )

    def test_no_dm_for_a_new_task_until_the_pilot_opts_in(self):
        self.assertEqual(self.post_task().status_code, 201)
        self.assertFalse(deliveries(self.pilot, TASKS_ASSIGNED_KEY).exists())
        say_yes(self.pilot, TASKS_ASSIGNED_KEY)
        self.post_task()
        delivery = deliveries(self.pilot, TASKS_ASSIGNED_KEY).get()
        self.assertIn("Write it", delivery.payload["discord_message"])

    def test_every_dm_starts_off_and_the_pilot_opts_in(self):
        prefs = self.client.get(
            "/api/tasks/preferences", **auth_headers(self.pilot)
        ).json()
        self.assertEqual(
            (prefs["dm_weekly"], prefs["dm_reminders"], prefs["dm_assigned"]),
            (False, False, False),
        )
        response = self.client.patch(
            "/api/tasks/preferences",
            data=json.dumps({"dm_reminders": True}),
            content_type="application/json",
            **auth_headers(self.pilot),
        )
        self.assertTrue(response.json()["dm_reminders"])
        self.assertFalse(response.json()["dm_weekly"])
        self.assertTrue(
            NotificationPreference.objects.filter(
                user=self.pilot,
                notification_type=TASKS_REMINDER_KEY,
                enabled=True,
            ).exists()
        )

    def test_quiet_hours(self):
        response = self.client.patch(
            "/api/tasks/preferences",
            data=json.dumps({"quiet_start": 22, "quiet_end": 8}),
            content_type="application/json",
            **auth_headers(self.pilot),
        )
        self.assertEqual(response.json()["quiet_start"], 22)
        response = self.client.patch(
            "/api/tasks/preferences",
            data=json.dumps({"quiet_start": 30}),
            content_type="application/json",
            **auth_headers(self.pilot),
        )
        self.assertEqual(response.status_code, 400)

    def test_digest_settings_are_for_task_admins(self):
        self.assertEqual(
            403,
            self.client.get(
                "/api/tasks/digest", **auth_headers(self.pilot)
            ).status_code,
        )
        response = self.client.patch(
            "/api/tasks/digest",
            data=json.dumps({"weekday": 0, "hour": 18}),
            content_type="application/json",
            **auth_headers(self.root),
        )
        self.assertEqual(response.json()["weekday"], 0)
        self.assertEqual(response.json()["hour"], 18)
