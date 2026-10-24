"""Tests for the technology-team alert and the user sync loop that uses it."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from discord.helpers import notify_technology_team
from discord.tasks import sync_discord_users


class TechnologyTeamAlertTestCase(TestCase):
    @patch("discord.helpers.discord")
    def test_alert_posts_location_and_detail(self, discord):
        self.assertTrue(notify_technology_team("job", "3 failed"))
        discord.create_message.assert_called_once()
        self.assertEqual(
            "Encountered error in job: 3 failed",
            discord.create_message.call_args.kwargs["message"],
        )

    @patch("discord.helpers.discord")
    def test_alert_never_raises(self, discord):
        discord.create_message.side_effect = RuntimeError("Discord is down")
        with self.assertLogs("discord.helpers", "WARNING"):
            self.assertFalse(notify_technology_team("job"))


@patch("discord.tasks.notify_technology_team")
@patch("discord.tasks.handle_discord_guild_member_error", return_value=False)
@patch("discord.tasks.sync_discord_user")
class SyncDiscordUsersTestCase(TestCase):
    def setUp(self):
        for name in ("a", "b", "c"):
            User.objects.create(username=name)

    def test_one_alert_after_the_loop(self, sync_user, unused_handle, alert):
        sync_user.side_effect = RuntimeError("boom")
        with self.assertLogs("discord.tasks", "ERROR"):
            failed = sync_discord_users()
        self.assertEqual(User.objects.count(), sync_user.call_count)
        self.assertEqual(User.objects.count(), failed)
        alert.assert_called_once_with(
            "sync_discord_users", f"{failed} user(s) failed; see logs"
        )

    def test_a_failing_user_does_not_stop_the_loop(
        self, sync_user, unused_handle, alert
    ):
        """Before, the alert was posted inside the except block, so a Discord
        outage raised there and aborted the run at the first bad user."""
        sync_user.side_effect = [RuntimeError("boom")] + [None] * (
            User.objects.count() - 1
        )
        with self.assertLogs("discord.tasks", "ERROR"):
            failed = sync_discord_users()
        self.assertEqual(1, failed)
        self.assertEqual(User.objects.count(), sync_user.call_count)
        alert.assert_called_once()

    def test_no_alert_when_everything_synced(
        self, sync_user, unused_handle, alert
    ):
        self.assertEqual(0, sync_discord_users())
        alert.assert_not_called()
