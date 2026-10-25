from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from ratelimit import RateLimitException
from requests import HTTPError

from app.test import TestCase
from discord.models import DiscordGuild
from eveonline.helpers.corporations.discord_bot import (
    INVITE_MAX_AGE,
    PROBE_LIMIT,
    DiscordBotError,
    authorize_url,
    bot_invite_url,
    corporation_discord_settings,
    guild_in_use,
    landing_channels,
    link_guild,
    page_invite_url,
    refresh_bot_invite,
    release_guild,
    unlink_guild,
)
from eveonline.models import EveCorporation
from tribes.models import Tribe, TribeExternalGuild, TribeGroup

CLIENT = "eveonline.helpers.corporations.discord_bot.DiscordClient"
GUILD_ID = 4242


def http_error(status: int, code: int | None = None) -> HTTPError:
    response = MagicMock(status_code=status)
    response.json.return_value = {"code": code} if code else {}
    return HTTPError(response=response)


def channel(cid, name="general", position=0, parent=None, kind=0, deny=0):
    overwrites = []
    if deny:
        overwrites.append({"id": str(GUILD_ID), "deny": str(deny)})
    return {
        "id": str(cid),
        "name": name,
        "type": kind,
        "position": position,
        "parent_id": str(parent) if parent else None,
        "permission_overwrites": overwrites,
    }


def new_invite(code="fresh", days=7):
    expires = timezone.now() + timedelta(days=days)
    return {"code": code, "expires_at": expires.isoformat()}


class LandingChannelsTestCase(SimpleTestCase):
    def test_orders_like_discord_and_skips_hidden_channels(self):
        channels = [
            channel(10, "Staff", position=0, kind=4, deny=1024),
            channel(11, "Public", position=1, kind=4),
            channel(20, "officers", position=0, parent=10),
            channel(21, "chat", position=1, parent=11),
            channel(22, "welcome", position=0, parent=11),
            channel(23, "voice", position=2, parent=11, kind=2),
            channel(24, "lobby", position=5),
            channel(25, "secret", position=3, parent=11, deny=1024),
        ]
        names = [c["name"] for c in landing_channels(channels, GUILD_ID)]
        # Outside any category first, then by category and position. The
        # staff category hides its channel, and voice can't hold an invite.
        self.assertEqual(["lobby", "welcome", "chat"], names)

    def test_channel_allow_beats_a_hidden_category(self):
        rules = channel(30, "rules", parent=10)
        rules["permission_overwrites"] = [
            {"id": str(GUILD_ID), "allow": "1024", "deny": "0"}
        ]
        channels = [channel(10, "Staff", kind=4, deny=1024), rules]
        self.assertEqual(
            ["rules"],
            [c["name"] for c in landing_channels(channels, GUILD_ID)],
        )

    def test_preferred_channel_first(self):
        channels = [channel(1, "a", position=0), channel(2, "b", position=1)]
        self.assertEqual(
            ["b", "a"],
            [
                c["name"]
                for c in landing_channels(channels, GUILD_ID, preferred=2)
            ],
        )


@override_settings(
    DISCORD_CLIENT_ID="client-1",
    DISCORD_CORP_BOT_REDIRECT_URL="https://api.example/cb",
)
class AuthorizeUrlTestCase(SimpleTestCase):
    def test_asks_only_for_invites(self):
        url = authorize_url("state-1")
        self.assertIn("scope=bot", url)
        # Create Instant Invite + View Channel, nothing else.
        self.assertIn("permissions=1025", url)
        self.assertIn("state=state-1", url)
        self.assertIn("redirect_uri=https%3A%2F%2Fapi.example%2Fcb", url)


class DiscordBotTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.corporation = EveCorporation.objects.create(
            corporation_id=98726134, name="Rattini Tribe"
        )

    def link(self, **guild):
        payload = {"id": str(GUILD_ID), "name": "Rattini", "icon": "abc"}
        payload.update(guild)
        return link_guild(self.corporation, payload, self.user)

    def connected(self, code="current", days=6, status="ok"):
        self.link(system_channel_id="77")
        self.corporation.discord_bot_status = status
        self.corporation.discord_bot_invite_code = code
        self.corporation.discord_bot_invite_expires_at = (
            timezone.now() + timedelta(days=days)
        )
        self.corporation.save()
        return self.corporation


class LinkGuildTestCase(DiscordBotTestCase):
    def test_links_the_server_and_waits_for_setup(self):
        self.assertIsNone(self.link(system_channel_id="77"))
        self.corporation.refresh_from_db()
        self.assertEqual("pending", self.corporation.discord_bot_status)
        self.assertEqual(GUILD_ID, self.corporation.discord_guild.guild_id)
        self.assertEqual(77, self.corporation.discord_bot_channel_id)
        self.assertEqual(self.user, self.corporation.discord_bot_linked_by)
        # Nobody gets the bot's link until it made an invite.
        self.assertIsNone(page_invite_url(self.corporation))

    @override_settings(DISCORD_GUILD_ID=GUILD_ID)
    def test_refuses_the_alliance_server(self):
        with self.assertRaises(DiscordBotError) as raised:
            self.link()
        self.assertEqual("alliance_server", raised.exception.code)
        self.corporation.refresh_from_db()
        self.assertIsNone(self.corporation.discord_guild)

    def test_another_server_releases_the_old_one(self):
        self.connected(code="old")
        previous = self.link(id="5555", name="New home")
        self.assertEqual(GUILD_ID, previous.guild_id)
        self.assertEqual("old", previous.invite_code)
        self.corporation.refresh_from_db()
        self.assertEqual("", self.corporation.discord_bot_invite_code)
        self.assertIsNone(self.corporation.discord_bot_channel_id)

    def test_same_server_keeps_its_invite(self):
        self.connected(code="keep")
        self.assertIsNone(self.link())
        self.corporation.refresh_from_db()
        self.assertEqual("keep", self.corporation.discord_bot_invite_code)
        self.assertEqual("pending", self.corporation.discord_bot_status)

    def test_unlink_falls_back_to_the_pasted_link(self):
        self.connected(code="bot")
        self.corporation.discord_invite_url = "https://discord.gg/pasted"
        self.corporation.save()
        self.assertEqual(
            "https://discord.gg/bot", page_invite_url(self.corporation)
        )
        release = unlink_guild(self.corporation)
        self.assertEqual(
            (GUILD_ID, "bot"), (release.guild_id, release.invite_code)
        )
        self.corporation.refresh_from_db()
        self.assertIsNone(self.corporation.discord_guild)
        self.assertEqual(
            "https://discord.gg/pasted", page_invite_url(self.corporation)
        )
        self.assertIsNone(unlink_guild(self.corporation))


class BotInviteUrlTestCase(DiscordBotTestCase):
    def test_only_working_invites_with_time_left(self):
        self.connected(code="ok1", days=2)
        self.assertEqual(
            "https://discord.gg/ok1", bot_invite_url(self.corporation)
        )
        self.corporation.discord_bot_invite_expires_at = (
            timezone.now() + timedelta(minutes=30)
        )
        self.assertIsNone(bot_invite_url(self.corporation))

        self.connected(status="no_permission")
        self.assertIsNone(bot_invite_url(self.corporation))

        self.connected()
        DiscordGuild.objects.filter(guild_id=GUILD_ID).update(is_active=False)
        self.corporation.refresh_from_db()
        self.assertIsNone(bot_invite_url(self.corporation))

    def test_admin_linked_guild_makes_no_invites(self):
        self.corporation.discord_guild = DiscordGuild.objects.create(
            guild_id=99, name="Hand linked"
        )
        self.corporation.discord_bot_invite_code = "stale"
        self.corporation.save()
        self.assertIsNone(bot_invite_url(self.corporation))
        self.assertIsNone(refresh_bot_invite(self.corporation))
        self.assertFalse(
            corporation_discord_settings(self.corporation)["bot"]["connected"]
        )

    def test_settings_say_which_link_the_page_shows(self):
        self.assertIsNone(
            corporation_discord_settings(self.corporation)["page_source"]
        )
        self.corporation.discord_invite_url = "https://discord.gg/pasted"
        self.corporation.save()
        self.assertEqual(
            "link",
            corporation_discord_settings(self.corporation)["page_source"],
        )
        self.connected()
        settings = corporation_discord_settings(self.corporation)
        self.assertEqual("bot", settings["page_source"])
        self.assertEqual("Rattini", settings["bot"]["guild_name"])
        self.assertEqual(
            "https://cdn.discordapp.com/icons/4242/abc.png?size=64",
            settings["bot"]["icon_url"],
        )


@patch(CLIENT)
class RefreshBotInviteTestCase(DiscordBotTestCase):
    def test_first_invite_in_the_system_channel(self, client_cls):
        client = client_cls.return_value
        client.create_channel_invite.return_value = {
            **new_invite("first"),
            "channel": {"name": "welcome"},
        }
        self.link(system_channel_id="77")

        self.assertEqual("ok", refresh_bot_invite(self.corporation))
        client.create_channel_invite.assert_called_once_with(
            77, INVITE_MAX_AGE
        )
        self.corporation.refresh_from_db()
        self.assertEqual("first", self.corporation.discord_bot_invite_code)
        self.assertEqual("welcome", self.corporation.discord_bot_channel_name)
        self.assertEqual(
            "https://discord.gg/first", page_invite_url(self.corporation)
        )

    def test_fresh_invite_is_only_checked(self, client_cls):
        client = client_cls.return_value
        self.connected(code="current", days=6)
        self.assertEqual("ok", refresh_bot_invite(self.corporation))
        client.get_invite.assert_called_once_with("current")
        client.create_channel_invite.assert_not_called()

    def test_rotates_with_three_days_left(self, client_cls):
        client = client_cls.return_value
        client.create_channel_invite.return_value = new_invite("next")
        self.connected(code="current", days=2)
        self.assertEqual("ok", refresh_bot_invite(self.corporation))
        client.get_invite.assert_not_called()
        self.corporation.refresh_from_db()
        self.assertEqual("next", self.corporation.discord_bot_invite_code)
        # The old invite is left to expire, not revoked.
        client.delete_invite.assert_not_called()

    def test_replaces_a_deleted_invite(self, client_cls):
        client = client_cls.return_value
        client.get_invite.side_effect = http_error(404, 10006)
        client.create_channel_invite.return_value = new_invite("again")
        self.connected(code="deleted", days=6)
        self.assertEqual("ok", refresh_bot_invite(self.corporation))
        self.corporation.refresh_from_db()
        self.assertEqual("again", self.corporation.discord_bot_invite_code)

    def test_moves_to_another_channel_when_the_old_one_went(self, client_cls):
        client = client_cls.return_value
        client.create_channel_invite.side_effect = [
            http_error(404, 10003),
            http_error(403, 50013),
            new_invite("moved"),
        ]
        client.get_guild_channels_raw.return_value = [
            channel(77, "deleted-one"),
            channel(80, "locked", position=1),
            channel(81, "open", position=2),
        ]
        self.link(system_channel_id="77")
        self.assertEqual("ok", refresh_bot_invite(self.corporation))
        tried = [
            c.args[0] for c in client.create_channel_invite.call_args_list
        ]
        self.assertEqual([77, 80, 81], tried)
        self.corporation.refresh_from_db()
        self.assertEqual(81, self.corporation.discord_bot_channel_id)
        self.assertEqual("open", self.corporation.discord_bot_channel_name)

    def test_no_permission_after_a_bounded_search(self, client_cls):
        client = client_cls.return_value
        client.create_channel_invite.side_effect = http_error(403, 50013)
        client.get_guild_channels_raw.return_value = [
            channel(100 + i, f"c{i}", position=i) for i in range(20)
        ]
        self.link()
        self.corporation.discord_invite_url = "https://discord.gg/pasted"
        self.corporation.save()
        self.assertEqual("no_permission", refresh_bot_invite(self.corporation))
        self.assertEqual(PROBE_LIMIT, client.create_channel_invite.call_count)
        # Visitors keep the pasted link meanwhile.
        self.assertEqual(
            "https://discord.gg/pasted", page_invite_url(self.corporation)
        )

    def test_removed_when_the_bot_is_out(self, client_cls):
        client = client_cls.return_value
        client.get_guild_channels_raw.side_effect = http_error(403, 50001)
        self.link()
        self.assertEqual("removed", refresh_bot_invite(self.corporation))

        # Known out and the guild sync agrees: no more Discord calls.
        DiscordGuild.objects.filter(guild_id=GUILD_ID).update(is_active=False)
        self.corporation.refresh_from_db()
        client_cls.reset_mock()
        self.assertIsNone(refresh_bot_invite(self.corporation))
        client_cls.return_value.get_guild_channels_raw.assert_not_called()

    def test_a_disconnect_during_the_refresh_wins(self, client_cls):
        client = client_cls.return_value
        self.link(system_channel_id="77")
        stale = EveCorporation.objects.select_related("discord_guild").get(
            pk=self.corporation.pk
        )

        def disconnect_meanwhile(*args):
            unlink_guild(
                EveCorporation.objects.select_related("discord_guild").get(
                    pk=self.corporation.pk
                )
            )
            return new_invite("late")

        client.create_channel_invite.side_effect = disconnect_meanwhile
        self.assertIsNone(refresh_bot_invite(stale))
        self.corporation.refresh_from_db()
        self.assertIsNone(self.corporation.discord_guild)
        self.assertEqual("", self.corporation.discord_bot_status)
        self.assertEqual("", self.corporation.discord_bot_invite_code)

    def test_discord_down_changes_nothing(self, client_cls):
        client = client_cls.return_value
        client.get_invite.side_effect = RateLimitException("slow", 5)
        self.connected(code="current", days=6)
        self.assertIsNone(refresh_bot_invite(self.corporation))
        client.get_invite.side_effect = http_error(503)
        self.assertIsNone(refresh_bot_invite(self.corporation))
        self.corporation.refresh_from_db()
        self.assertEqual("ok", self.corporation.discord_bot_status)
        self.assertEqual("current", self.corporation.discord_bot_invite_code)


@patch(CLIENT)
class ReleaseGuildTestCase(DiscordBotTestCase):
    def test_leaves_a_server_nothing_uses(self, client_cls):
        client = client_cls.return_value
        DiscordGuild.objects.create(guild_id=GUILD_ID, name="Rattini")
        self.assertTrue(release_guild(GUILD_ID, "old"))
        client.delete_invite.assert_called_once_with("old")
        client.leave_guild.assert_called_once_with(GUILD_ID)
        self.assertFalse(DiscordGuild.objects.get(guild_id=GUILD_ID).is_active)

    def test_stays_where_another_corporation_or_tribe_uses_it(
        self, client_cls
    ):
        client = client_cls.return_value
        self.connected(code="theirs")
        self.assertTrue(guild_in_use(GUILD_ID))
        self.assertFalse(release_guild(GUILD_ID, "mine"))
        client.delete_invite.assert_called_once_with("mine")
        client.leave_guild.assert_not_called()

        unlink_guild(self.corporation)
        tribe = Tribe.objects.create(name="Pulse", slug="pulse")
        group = TribeGroup.objects.create(
            tribe=tribe, name="Fishermen", code="pulse.fishermen"
        )
        TribeExternalGuild.objects.create(
            tribe_group=group,
            guild=DiscordGuild.objects.get(guild_id=GUILD_ID),
            member_role_id=1,
        )
        self.assertFalse(release_guild(GUILD_ID, ""))
        client.leave_guild.assert_not_called()

    def test_keeps_an_invite_a_reconnect_still_uses(self, client_cls):
        client = client_cls.return_value
        self.connected(code="kept")
        release_guild(GUILD_ID, "kept")
        client.delete_invite.assert_not_called()

    @override_settings(DISCORD_GUILD_ID=GUILD_ID)
    def test_never_leaves_the_alliance_server(self, client_cls):
        self.assertFalse(release_guild(GUILD_ID, ""))
        client_cls.return_value.leave_guild.assert_not_called()


class GuildInUseTestCase(DiscordBotTestCase):
    def test_hand_linked_corporations_count(self):
        guild = DiscordGuild.objects.create(guild_id=7, name="Ops")
        self.assertFalse(guild_in_use(7))
        other = EveCorporation.objects.create(
            corporation_id=1001, name="Other", discord_guild=guild
        )
        self.assertTrue(guild_in_use(7))
        other.delete()
        self.assertFalse(guild_in_use(7))
