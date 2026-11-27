"""The hourly job that posts each group's daily fleet roundup."""

from datetime import date, datetime, timezone as dt_timezone
from unittest.mock import patch

from django.db.models import signals
from django.test import override_settings

from app.test import TestCase
from discord.models import DiscordGuild
from eveonline.models import EveCorporation
from fleets.models import EveFleet
from tribes.models import TribeGroupCorporationFollow
from tribes.tasks import post_group_fleet_roundups
from tribes.tests.publishing_fixtures import (
    GROUP_CHANNEL_ID,
    add_member,
    make_tribe_group,
    make_user,
)

DESTINATIONS = "tribes.helpers.fleet_post_destinations"


def eve(day: int, hour: int) -> datetime:
    return datetime(2026, 12, day, hour, 0, tzinfo=dt_timezone.utc)


def setUpModule():
    signals.post_save.disconnect(
        sender=EveFleet, dispatch_uid="update_fleet_schedule_on_save"
    )


def tearDownModule():
    # pylint: disable-next=import-outside-toplevel
    from fleets.signals import update_fleet_schedule_on_save

    signals.post_save.connect(
        update_fleet_schedule_on_save,
        sender=EveFleet,
        dispatch_uid="update_fleet_schedule_on_save",
    )


@override_settings(DISCORD_FLEET_EMOJIS={})
@patch(f"{DESTINATIONS}.on_commit_enqueue")
@patch(f"{DESTINATIONS}.queue_channel_message")
class GroupRoundupTaskTests(TestCase):
    def setUp(self):
        super().setUp()
        self.group = make_tribe_group(
            name="Mining",
            code="industry.mining",
            roundup_enabled=True,
            roundup_hour=20,
        )
        fc = make_user("miner_fc")
        add_member(self.group, fc)
        EveFleet.objects.create(
            type="non_strategic",
            description="Mining op",
            start_time=eve(2, 18),
            created_by=fc,
            host_group=self.group,
            status="pending",
        )

    def run_at(self, when):
        with patch("tribes.tasks.timezone.now", return_value=when):
            post_group_fleet_roundups()
        self.group.refresh_from_db()

    def test_posts_at_hour(self, queue, enqueue):
        self.run_at(eve(1, 20))
        queue.assert_called_once()
        self.assertEqual(queue.call_args.args[0], GROUP_CHANNEL_ID)
        payload = queue.call_args.kwargs["payload"]
        self.assertTrue(payload["content"].startswith("### Mining fleets"))
        self.assertEqual(payload["flags"], 4096)
        self.assertEqual(self.group.roundup_last_sent_on, date(2026, 12, 1))
        enqueue.assert_not_called()

    def test_not_before_hour(self, queue, enqueue):
        self.run_at(eve(1, 19))
        queue.assert_not_called()
        self.assertIsNone(self.group.roundup_last_sent_on)

    def test_missed_hour_posts_once_later(self, queue, enqueue):
        self.run_at(eve(1, 21))
        self.run_at(eve(1, 22))
        self.run_at(eve(1, 23))
        queue.assert_called_once()
        self.run_at(eve(2, 20))
        self.assertEqual(queue.call_count, 1)  # nothing in days 3-7

    def test_disabled_group_never_posts(self, queue, enqueue):
        self.group.roundup_enabled = False
        self.group.save()
        self.run_at(eve(1, 20))
        queue.assert_not_called()

    def test_no_fleets_marks_day_without_post(self, queue, enqueue):
        self.run_at(eve(3, 20))
        queue.assert_not_called()
        self.assertEqual(self.group.roundup_last_sent_on, date(2026, 12, 3))

    def test_roundup_reaches_approved_corp(self, queue, enqueue):
        corporation = EveCorporation.objects.create(
            corporation_id=98838663,
            name="M-EXC",
            discord_guild=DiscordGuild.objects.create(guild_id=4100, name="M"),
            discord_bot_status=EveCorporation.DISCORD_BOT_OK,
        )
        follow = TribeGroupCorporationFollow.objects.create(
            tribe_group=self.group,
            corporation=corporation,
            channel_id=880000111,
            status=TribeGroupCorporationFollow.STATUS_APPROVED,
        )
        self.run_at(eve(1, 20))
        queue.assert_called_once()
        args = enqueue.call_args.args[1]
        self.assertEqual(args[0], follow.id)
        self.assertEqual(args[1]["flags"], 4096)
        self.assertEqual(args[1]["allowed_mentions"], {"parse": []})
