"""Where a group fleet post goes: the group's channel and the corporation
channels its chiefs approved (docs/tribes/group-fleet-roundup.md)."""

from unittest.mock import patch

import requests

from app.test import TestCase
from discord.models import DiscordGuild
from eveonline.models import EveCorporation
from tribes.helpers.fleet_post_destinations import (
    Destination,
    group_post_destinations,
    send_group_post,
)
from tribes.models import TribeGroupCorporationFollow
from tribes.tasks import post_forwarded_fleet_message
from tribes.tests.publishing_fixtures import (
    GROUP_CHANNEL_ID,
    ROLE_ID,
    make_tribe_group,
)

CORP_CHANNEL_ID = 880000111
START_PING = {"content": f"<@&{ROLE_ID}>", "embeds": [{"title": "Go"}]}
PRE_PING = {"content": "", "embeds": [{"title": "Soon"}], "flags": 4096}


def discord_http_error(code: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = 403
    response._content = (  # pylint: disable=protected-access
        b'{"code": %d, "message": "nope"}' % code
    )
    return requests.HTTPError(response=response)


class FleetPostDestinationTests(TestCase):
    def setUp(self):
        super().setUp()
        self.group = make_tribe_group(name="Mining", code="industry.mining")
        guild = DiscordGuild.objects.create(guild_id=4100, name="M-EXC")
        self.corporation = EveCorporation.objects.create(
            corporation_id=98838663,
            name="M-EXC",
            discord_guild=guild,
            discord_bot_status=EveCorporation.DISCORD_BOT_OK,
        )

    def follow(self, status="approved", **fields):
        return TribeGroupCorporationFollow.objects.create(
            tribe_group=self.group,
            corporation=fields.pop("corporation", self.corporation),
            channel_id=CORP_CHANNEL_ID,
            channel_name="mining-pings",
            status=status,
            **fields,
        )

    def test_group_channel_only_without_follows(self):
        self.assertEqual(
            group_post_destinations(self.group, "roundup"),
            [Destination(channel_id=GROUP_CHANNEL_ID, follow_id=None)],
        )

    def test_approved_follow_is_a_destination(self):
        follow = self.follow()
        self.assertEqual(
            group_post_destinations(self.group, "pre_ping"),
            [
                Destination(channel_id=GROUP_CHANNEL_ID, follow_id=None),
                Destination(channel_id=CORP_CHANNEL_ID, follow_id=follow.id),
            ],
        )

    def test_requested_and_revoked_follows_skipped(self):
        self.follow(status="requested")
        other = EveCorporation.objects.create(
            corporation_id=1002,
            name="Other",
            discord_guild=DiscordGuild.objects.create(guild_id=4200, name="O"),
            discord_bot_status=EveCorporation.DISCORD_BOT_OK,
        )
        self.follow(status="revoked", corporation=other)
        self.assertEqual(
            len(group_post_destinations(self.group, "roundup")), 1
        )

    def test_follow_skipped_when_bot_not_ok(self):
        self.follow()
        self.corporation.discord_bot_status = (
            EveCorporation.DISCORD_BOT_REMOVED
        )
        self.corporation.save()
        self.assertEqual(
            len(group_post_destinations(self.group, "roundup")), 1
        )

    def test_roundup_and_pre_ping_silent_everywhere(self):
        follow = self.follow()
        for kind in ("roundup", "pre_ping"):
            for dest in group_post_destinations(self.group, kind):
                payload = dest.apply(PRE_PING, kind)
                self.assertEqual(payload["flags"], 4096, (kind, dest))
                self.assertEqual(payload["allowed_mentions"], {"parse": []})
                self.assertEqual(payload["embeds"], PRE_PING["embeds"])
        self.assertTrue(follow.is_forwarding())

    def test_start_ping_role_in_group_here_in_corp(self):
        self.follow()
        group_dest, corp_dest = group_post_destinations(
            self.group, "start_ping"
        )
        self.assertEqual(
            group_dest.apply(START_PING, "start_ping"), START_PING
        )
        corp = corp_dest.apply(START_PING, "start_ping")
        self.assertEqual(corp["content"], "@here")
        self.assertNotIn("<@&", corp["content"])
        self.assertEqual(corp["allowed_mentions"], {"parse": ["everyone"]})
        self.assertNotIn("flags", corp)
        self.assertEqual(corp["embeds"], START_PING["embeds"])
        self.assertEqual(START_PING["content"], f"<@&{ROLE_ID}>")

    @patch("tribes.helpers.fleet_post_destinations.on_commit_enqueue")
    @patch("tribes.helpers.fleet_post_destinations.queue_channel_message")
    def test_send_group_post_queues_each(self, queue_channel, enqueue):
        follow = self.follow()
        queued = send_group_post(self.group, "start_ping", START_PING, "t")
        self.assertEqual(queued, 2)
        queue_channel.assert_called_once()
        self.assertEqual(queue_channel.call_args.args[0], GROUP_CHANNEL_ID)
        self.assertEqual(queue_channel.call_args.kwargs["payload"], START_PING)
        task, args = enqueue.call_args.args[:2]
        self.assertIs(task, post_forwarded_fleet_message)
        self.assertEqual(args[0], follow.id)
        self.assertEqual(args[1]["content"], "@here")

    @patch("tribes.tasks.DiscordClient")
    def test_forward_task_posts_and_records(self, client):
        follow = self.follow()
        self.assertTrue(post_forwarded_fleet_message(follow.id, PRE_PING, "t"))
        client.return_value.create_message.assert_called_once_with(
            channel_id=CORP_CHANNEL_ID, payload=PRE_PING
        )
        follow.refresh_from_db()
        self.assertTrue(follow.last_delivery_ok)
        self.assertEqual(follow.last_delivery_error, "")
        self.assertIsNotNone(follow.last_delivery_at)

    @patch("tribes.tasks.DiscordClient")
    def test_forward_task_drops_revoked_follow(self, client):
        follow = self.follow()
        follow.status = "revoked"
        follow.save()
        self.assertFalse(
            post_forwarded_fleet_message(follow.id, PRE_PING, "t")
        )
        client.return_value.create_message.assert_not_called()
        self.assertFalse(post_forwarded_fleet_message(999999, PRE_PING, "t"))

    @patch("tribes.tasks.DiscordClient")
    def test_forward_task_records_missing_access(self, client):
        follow = self.follow()
        client.return_value.create_message.side_effect = discord_http_error(
            50001
        )
        self.assertFalse(
            post_forwarded_fleet_message(follow.id, PRE_PING, "t")
        )
        follow.refresh_from_db()
        self.assertFalse(follow.last_delivery_ok)
        self.assertEqual(follow.last_delivery_error, "missing_access")

    @patch("tribes.tasks.DiscordClient")
    def test_forward_task_records_unknown_error(self, client):
        follow = self.follow()
        client.return_value.create_message.side_effect = RuntimeError("x")
        self.assertFalse(
            post_forwarded_fleet_message(follow.id, PRE_PING, "t")
        )
        follow.refresh_from_db()
        self.assertEqual(follow.last_delivery_error, "error")
