from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from requests import ConnectionError as RequestsConnectionError
from requests import HTTPError

from app.test import TestCase
from eveonline.helpers.corporations.discord_invite import (
    DiscordInviteError,
    check_invite,
    discord_settings,
    parse_invite_code,
    public_invite_url,
    recheck_discord_invite,
    remove_discord_invite,
    save_discord_invite,
)
from eveonline.models import EveCorporation

GET_INVITE = (
    "eveonline.helpers.corporations.discord_invite.DiscordClient.get_invite"
)


def invite(expires_at=None, guild=True):
    return {
        "code": "rattini",
        "expires_at": expires_at,
        "guild": (
            {"id": "4242", "name": "Rattini Tribe", "icon": "abc123"}
            if guild
            else None
        ),
    }


def not_found():
    response = MagicMock(status_code=404)
    return HTTPError(response=response)


class ParseInviteCodeTestCase(SimpleTestCase):
    def test_accepts_discord_invite_links(self):
        for value in (
            "https://discord.gg/rattini",
            "discord.gg/rattini",
            "https://discord.gg/rattini?event=1",
            "https://discord.com/invite/rattini",
            "https://www.discordapp.com/invite/rattini/",
            "  https://DISCORD.GG/rattini  ",
        ):
            self.assertEqual("rattini", parse_invite_code(value), value)

    def test_keeps_hyphenated_codes(self):
        self.assertEqual(
            "a-rat-join", parse_invite_code("discord.gg/a-rat-join")
        )

    def test_rejects_other_links(self):
        for value in (
            "https://example.com/rattini",
            "https://discord.com/channels/1/2",
            "https://discord.gg/",
            "https://discord.gg/bad code",
            "https://discord.gg/a/b",
            "https://evil.discord.gg.example.com/rattini",
        ):
            with self.assertRaises(DiscordInviteError, msg=value) as ctx:
                parse_invite_code(value)
            self.assertEqual("not_discord_invite", ctx.exception.code)

    def test_requires_a_link(self):
        with self.assertRaises(DiscordInviteError) as ctx:
            parse_invite_code("  ")
        self.assertEqual("url_required", ctx.exception.code)


class CheckInviteTestCase(SimpleTestCase):
    @patch(GET_INVITE, return_value=invite())
    def test_permanent_invite(self, mock_get):
        code, resolved = check_invite("discord.gg/rattini")
        self.assertEqual("rattini", code)
        self.assertEqual(4242, resolved.guild_id)
        self.assertEqual("Rattini Tribe", resolved.guild_name)

    @patch(
        GET_INVITE, return_value=invite(expires_at="2026-11-01T00:00:00+00:00")
    )
    def test_refuses_invites_that_expire(self, mock_get):
        with self.assertRaises(DiscordInviteError) as ctx:
            check_invite("discord.gg/rattini")
        self.assertEqual("invite_expires", ctx.exception.code)

    @patch(GET_INVITE, side_effect=not_found())
    def test_unknown_invite(self, mock_get):
        with self.assertRaises(DiscordInviteError) as ctx:
            check_invite("discord.gg/rattini")
        self.assertEqual("invite_not_found", ctx.exception.code)

    @patch(GET_INVITE, return_value=invite(guild=False))
    def test_group_dm_invite(self, mock_get):
        with self.assertRaises(DiscordInviteError) as ctx:
            check_invite("discord.gg/rattini")
        self.assertEqual("not_a_server", ctx.exception.code)

    @patch(GET_INVITE, side_effect=RequestsConnectionError())
    def test_discord_unreachable_is_unchecked(self, mock_get):
        code, resolved = check_invite("discord.gg/rattini")
        self.assertEqual("rattini", code)
        self.assertIsNone(resolved)


class CorporationInviteTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.corporation = EveCorporation.objects.create(
            corporation_id=98726134, name="Rattini Tribe"
        )

    def reload(self):
        self.corporation.refresh_from_db()
        return self.corporation

    @patch(GET_INVITE, return_value=invite())
    def test_save_stores_the_server(self, mock_get):
        save_discord_invite(
            self.corporation, "https://discord.com/invite/rattini"
        )
        corporation = self.reload()
        self.assertEqual(
            "https://discord.gg/rattini", corporation.discord_invite_url
        )
        settings = discord_settings(corporation)
        self.assertEqual("ok", settings["status"])
        self.assertEqual("Rattini Tribe", settings["guild_name"])
        self.assertEqual(
            "https://cdn.discordapp.com/icons/4242/abc123.png?size=64",
            settings["icon_url"],
        )
        self.assertEqual(
            "https://discord.gg/rattini", public_invite_url(corporation)
        )

    @patch(GET_INVITE, side_effect=RequestsConnectionError())
    def test_save_while_discord_is_down_is_unchecked_and_public(
        self, mock_get
    ):
        save_discord_invite(self.corporation, "discord.gg/rattini")
        corporation = self.reload()
        self.assertEqual("unchecked", discord_settings(corporation)["status"])
        self.assertEqual(
            "https://discord.gg/rattini", public_invite_url(corporation)
        )

    def test_no_discord(self):
        settings = discord_settings(self.corporation)
        self.assertFalse(settings["exists"])
        self.assertIsNone(settings["status"])
        self.assertIsNone(public_invite_url(self.corporation))

    @patch(GET_INVITE, return_value=invite())
    def test_dead_invite_is_hidden_until_replaced(self, get):
        save_discord_invite(self.corporation, "discord.gg/rattini")
        get.side_effect = not_found()
        self.assertEqual(
            EveCorporation.DISCORD_INVITE_DEAD,
            recheck_discord_invite(self.reload()),
        )
        corporation = self.reload()
        self.assertEqual("dead", discord_settings(corporation)["status"])
        self.assertIsNone(public_invite_url(corporation))
        # The settings still show which server it was.
        self.assertEqual(
            "Rattini Tribe", discord_settings(corporation)["guild_name"]
        )

        get.side_effect = None
        get.return_value = invite()
        save_discord_invite(corporation, "discord.gg/rattini")
        self.assertEqual(
            "https://discord.gg/rattini", public_invite_url(self.reload())
        )

    @patch(GET_INVITE, side_effect=RequestsConnectionError())
    def test_recheck_leaves_status_when_discord_is_down(self, mock_get):
        self.corporation.discord_invite_url = "https://discord.gg/rattini"
        self.corporation.discord_invite_status = (
            EveCorporation.DISCORD_INVITE_OK
        )
        self.corporation.save()
        self.assertIsNone(recheck_discord_invite(self.corporation))
        self.assertEqual("ok", discord_settings(self.reload())["status"])

    @patch(GET_INVITE)
    def test_recheck_skips_corporations_without_discord(self, get):
        self.assertIsNone(recheck_discord_invite(self.corporation))
        get.assert_not_called()

    @patch(GET_INVITE, return_value=invite())
    def test_remove_clears_everything(self, mock_get):
        save_discord_invite(self.corporation, "discord.gg/rattini")
        remove_discord_invite(self.reload())
        corporation = self.reload()
        self.assertEqual("", corporation.discord_invite_url)
        self.assertEqual("", corporation.discord_invite_guild_name)
        self.assertFalse(discord_settings(corporation)["exists"])
