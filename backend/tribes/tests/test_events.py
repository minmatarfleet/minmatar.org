"""Tribe group events: API rules, Discord calls (mocked), interest sync."""

from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.test import Client, override_settings
from django.utils import timezone

from app.test import TestCase
from app.testing import make_token
from tribes.helpers import event_sync
from tribes.helpers.events import discord_event_payload, recurrence_rule
from tribes.models import TribeEvent, TribeGroup
from tribes.tests.publishing_fixtures import (
    GROUP_CHANNEL_ID,
    ROLE_ID,
    add_member,
    make_tribe_group,
    make_user,
)

BASE_URL = "/api/tribes"
VOICE_ID = 9001
STAGE_ID = 9002
CHANNELS = [
    {"id": GROUP_CHANNEL_ID, "name": "dreads", "type": "text"},
    {"id": VOICE_ID, "name": "Fleet Comms", "type": "voice"},
    {"id": STAGE_ID, "name": "Town Hall", "type": "stage"},
]


@override_settings(DISCORD_GUILD_ID=1041384161505722368)
@patch("tribes.helpers.discord_channels.guild_channels", return_value=CHANNELS)
class TribeEventTests(TestCase):
    def setUp(self):
        super().setUp()
        self.group = make_tribe_group()
        self.member = make_user("member")
        add_member(self.group, self.member)
        self.chief = make_user("chief")
        self.group.chief = self.chief
        self.group.save()
        self.outsider = make_user("outsider")
        self.start = (timezone.now() + timedelta(days=3)).replace(
            microsecond=0
        )

    def call(self, method, path, user=None, data=None):
        kwargs = {}
        if user is not None:
            kwargs["HTTP_AUTHORIZATION"] = f"Bearer {make_token(user)}"
        if data is not None:
            kwargs["data"] = data
            kwargs["content_type"] = "application/json"
        return getattr(Client(), method)(f"{BASE_URL}{path}", **kwargs)

    def payload(self, **fields):
        data = {
            "title": "Dread practice",
            "description": "Bring a dread.",
            "starts_at": self.start.isoformat(),
            "where_kind": "voice",
            "voice_channel_id": str(VOICE_ID),
        }
        data.update(fields)
        return data

    def create(self, user=None, **fields):
        with patch(
            "tribes.tasks.create_tribe_discord_event.apply_async"
        ) as queued, self.captureOnCommitCallbacks(execute=True):
            response = self.call(
                "post",
                f"/groups/{self.group.id}/events",
                user or self.chief,
                self.payload(**fields),
            )
        return response, queued

    def event(self, **fields):
        values = {
            "tribe_group": self.group,
            "created_by": self.chief,
            "title": "Dread practice",
            "starts_at": self.start,
            "where_kind": "voice",
            "voice_channel_id": VOICE_ID,
            "voice_channel_name": "Fleet Comms",
        }
        values.update(fields)
        return TribeEvent.objects.create(**values)

    def test_create_needs_event_right(self, channels):
        response, queued = self.create(self.member)
        self.assertEqual(response.status_code, 403)
        queued.assert_not_called()

        self.group.event_policy = TribeGroup.POLICY_MEMBERS
        self.group.save()
        response, queued = self.create(self.member)
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["voice_channel_name"], "Fleet Comms")
        self.assertEqual(body["voice_channel_id"], str(VOICE_ID))
        self.assertEqual(body["tribe_group"]["name"], "Dreads")
        self.assertTrue(body["can_manage"])
        self.assertIsNone(body["discord_event_url"])
        queued.assert_called_once_with(args=(body["id"],))

    def test_create_validation(self, channels):
        cases = [
            {
                "where_kind": "place",
                "location": "Amamake",
                "members_only": True,
                "ends_at": (self.start + timedelta(hours=1)).isoformat(),
            },
            {"where_kind": "place", "location": "Amamake"},
            {"where_kind": "place", "location": ""},
            {"voice_channel_id": str(GROUP_CHANNEL_ID)},
            {"voice_channel_id": None},
            {"starts_at": (timezone.now() - timedelta(hours=1)).isoformat()},
            {"ends_at": (self.start - timedelta(hours=1)).isoformat()},
        ]
        for fields in cases:
            with self.subTest(fields=fields):
                response, queued = self.create(**fields)
                self.assertEqual(response.status_code, 400, response.content)
                queued.assert_not_called()
        self.assertFalse(TribeEvent.objects.exists())

    def test_discord_payloads(self, channels):
        voice = self.event(description="Bring a dread.")
        payload = discord_event_payload(voice)
        self.assertEqual(payload["entity_type"], 2)
        self.assertEqual(payload["channel_id"], str(VOICE_ID))
        self.assertEqual(payload["privacy_level"], 2)
        self.assertTrue(payload["description"].startswith("Hosted by Dreads."))
        self.assertIsNone(payload["recurrence_rule"])

        stage = self.event(voice_channel_id=STAGE_ID)
        self.assertEqual(discord_event_payload(stage)["entity_type"], 1)

        place = self.event(
            where_kind="place",
            voice_channel_id=None,
            location="Amamake VI",
            ends_at=self.start + timedelta(hours=2),
        )
        payload = discord_event_payload(place)
        self.assertEqual(payload["entity_type"], 3)
        self.assertEqual(
            payload["entity_metadata"], {"location": "Amamake VI"}
        )
        self.assertIsNone(payload["channel_id"])
        self.assertIn("scheduled_end_time", payload)

    def test_recurrence_rules(self, channels):
        # Saturday 2026-11-14 is the 2nd Saturday of November.
        start = datetime(2026, 11, 14, 19, 0, tzinfo=dt_timezone.utc)
        weekly = self.event(starts_at=start, recurrence="weekly")
        self.assertEqual(
            recurrence_rule(weekly),
            {
                "start": start.isoformat(),
                "interval": 1,
                "frequency": 2,
                "by_weekday": [5],
            },
        )
        monthly = self.event(starts_at=start, recurrence="monthly")
        self.assertEqual(
            recurrence_rule(monthly)["by_n_weekday"], [{"n": 2, "day": 5}]
        )
        self.assertEqual(recurrence_rule(monthly)["frequency"], 1)

    @patch("tribes.helpers.event_sync.queue_channel_message")
    @patch("tribes.helpers.event_sync.DiscordClient")
    def test_create_task_creates_event_and_announces(
        self, client, queue, channels
    ):
        client.return_value.create_scheduled_event.return_value = {
            "id": "1300000000000000001"
        }
        event = self.event()
        self.assertTrue(event_sync.create_discord_event(event.id))
        sent = client.return_value.create_scheduled_event.call_args[0][0]
        self.assertEqual(sent["name"], "Dread practice")
        event.refresh_from_db()
        self.assertEqual(event.discord_event_id, 1300000000000000001)
        queue.assert_called_once()
        self.assertEqual(queue.call_args[0][0], GROUP_CHANNEL_ID)
        message = queue.call_args[1]["message"]
        self.assertTrue(
            message.startswith(f"<@&{ROLE_ID}> **Dread practice**")
        )
        self.assertTrue(
            message.endswith(
                "\nhttps://discord.com/events/1041384161505722368/"
                "1300000000000000001"
            )
        )
        self.assertEqual(message.count("\n"), 1)

    @patch("tribes.helpers.event_sync.queue_channel_message")
    @patch("tribes.helpers.event_sync.DiscordClient")
    def test_no_announcement_when_off(self, client, queue, channels):
        client.return_value.create_scheduled_event.return_value = {"id": "5"}
        event_sync.create_discord_event(self.event(announce=False).id)
        queue.assert_not_called()

    @patch("tribes.helpers.event_sync.DiscordClient")
    def test_edit_and_cancel(self, client, channels):
        event = self.event(discord_event_id=42)
        with patch(
            "tribes.tasks.update_tribe_discord_event.apply_async"
        ) as queued, self.captureOnCommitCallbacks(execute=True):
            response = self.call(
                "patch",
                f"/events/{event.id}",
                self.member,
                {"title": "Nope"},
            )
            self.assertEqual(response.status_code, 403)
            response = self.call(
                "patch",
                f"/events/{event.id}",
                self.chief,
                {"title": "Dread practice II", "recurrence": "weekly"},
            )
        self.assertEqual(response.status_code, 200, response.content)
        queued.assert_called_once_with(args=(event.id,))
        self.assertEqual(
            response.json()["recurrence_label"],
            "Every "
            + (
                (
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                )[self.start.weekday()]
            ),
        )

        event_sync.update_discord_event(event.id)
        event_id, sent = client.return_value.edit_scheduled_event.call_args[0]
        self.assertEqual(event_id, 42)
        self.assertEqual(sent["name"], "Dread practice II")
        self.assertEqual(sent["recurrence_rule"]["frequency"], 2)

        response = self.call(
            "patch",
            f"/events/{event.id}",
            self.chief,
            {
                "where_kind": "place",
                "location": "Amamake",
                "members_only": True,
            },
        )
        self.assertEqual(response.status_code, 400)

        with patch(
            "tribes.tasks.cancel_tribe_discord_event.apply_async"
        ) as queued, self.captureOnCommitCallbacks(execute=True):
            response = self.call(
                "post", f"/events/{event.id}/cancel", self.chief
            )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["status"], "cancelled")
        queued.assert_called_once_with(args=(event.id,))
        event_sync.cancel_discord_event(event.id)
        self.assertEqual(
            client.return_value.edit_scheduled_event.call_args[0],
            (42, {"status": 4}),
        )
        # Cancelled in the last day: still listed.
        listed = self.call("get", f"/groups/{self.group.id}/events").json()
        self.assertEqual([row["status"] for row in listed], ["cancelled"])
        self.assertEqual(
            self.call(
                "post", f"/events/{event.id}/cancel", self.chief
            ).status_code,
            400,
        )

    def test_list_hides_members_only_events(self, channels):
        public = self.event(title="Public")
        hidden = self.event(title="Hidden", members_only=True)
        self.event(
            title="Old",
            starts_at=timezone.now() - timedelta(days=1),
        )
        path = f"/groups/{self.group.id}/events"
        anonymous = [row["id"] for row in self.call("get", path).json()]
        self.assertEqual(anonymous, [public.id])
        outsider = [
            row["id"] for row in self.call("get", path, self.outsider).json()
        ]
        self.assertEqual(outsider, [public.id])
        member = [
            row["id"] for row in self.call("get", path, self.member).json()
        ]
        self.assertEqual(sorted(member), sorted([public.id, hidden.id]))
        rows = self.call("get", path, self.member).json()
        self.assertFalse(any(row["can_manage"] for row in rows))
        rows = self.call("get", path, self.chief).json()
        self.assertTrue(all(row["can_manage"] for row in rows))

    def test_announcement_preview(self, channels):
        path = f"/groups/{self.group.id}/events/announcement-preview"
        self.assertEqual(
            self.call("post", path, self.member, self.payload()).status_code,
            403,
        )
        response = self.call(
            "post", path, self.chief, self.payload(recurrence="monthly")
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["channel_name"], "dreads")
        self.assertTrue(body["content"].startswith(f"<@&{ROLE_ID}> "))
        self.assertTrue(
            body["content"].endswith(
                "https://discord.com/events/1041384161505722368/new"
            )
        )
        self.assertEqual(body["event_preview"]["where_label"], "Fleet Comms")
        self.assertIn(
            "of the month", body["event_preview"]["recurrence_label"]
        )
        self.assertFalse(TribeEvent.objects.exists())
        response = self.call(
            "post", path, self.chief, self.payload(announce=False)
        )
        self.assertIsNone(response.json()["content"])

    @patch("tribes.helpers.event_sync.DiscordClient")
    def test_interest_sync(self, client, channels):
        now = timezone.now()
        upcoming = self.event(discord_event_id=1)
        finished = self.event(
            discord_event_id=2,
            starts_at=now - timedelta(hours=5),
            ends_at=now - timedelta(hours=3),
        )
        weekly = self.event(
            discord_event_id=3,
            recurrence="weekly",
            starts_at=now - timedelta(days=1),
            ends_at=now - timedelta(days=1) + timedelta(hours=2),
        )
        gone = self.event(
            discord_event_id=4,
            recurrence="weekly",
            starts_at=now - timedelta(days=1),
        )
        next_week = (weekly.starts_at + timedelta(days=7)).isoformat()
        client.return_value.list_scheduled_events.return_value = [
            {"id": "1", "user_count": 12, "scheduled_start_time": None},
            {"id": "3", "user_count": 4, "scheduled_start_time": next_week},
        ]
        event_sync.sync_event_interest()
        client.return_value.list_scheduled_events.assert_called_once_with(
            with_user_count=True
        )
        for event in (upcoming, finished, weekly, gone):
            event.refresh_from_db()
        self.assertEqual(upcoming.interested_count, 12)
        self.assertEqual(upcoming.status, "scheduled")
        self.assertEqual(finished.status, "completed")
        self.assertEqual(weekly.interested_count, 4)
        self.assertEqual(weekly.status, "scheduled")
        self.assertEqual(weekly.starts_at.isoformat(), next_week)
        self.assertEqual(weekly.ends_at - weekly.starts_at, timedelta(hours=2))
        self.assertEqual(gone.status, "completed")

    def test_beat_runs_interest_sync(self, channels):
        # pylint: disable-next=import-outside-toplevel
        from django.conf import settings

        entry = settings.CELERYBEAT_SCHEDULE[
            "[Tribes] Sync group event interest"
        ]
        self.assertEqual(
            entry["task"], "tribes.tasks.sync_tribe_event_interest"
        )
