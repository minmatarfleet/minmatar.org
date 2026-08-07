"""Tests for affiliation error logging hygiene (CELERY-M)."""

from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User

from app.test import TestCase
from discord.exceptions import DiscordRoleAssignmentError
from groups.tasks import log_affiliation_update_error


class LogAffiliationUpdateErrorTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="pilot")

    @patch("groups.tasks.user_primary_character")
    @patch(
        "groups.tasks.handle_discord_guild_member_error", return_value=False
    )
    @patch("groups.tasks.logger")
    def test_member_not_on_server_logs_info(
        self, mock_logger, mock_handle, mock_primary
    ):
        mock_primary.return_value = MagicMock()
        exc = DiscordRoleAssignmentError(
            "Cannot add user 1 to Discord role Guest: "
            "member not on Discord server"
        )
        log_affiliation_update_error(self.user, exc)
        mock_logger.info.assert_called()
        mock_logger.error.assert_not_called()
        self.assertTrue(mock_handle.called)

    @patch("groups.tasks.user_primary_character")
    @patch(
        "groups.tasks.handle_discord_guild_member_error", return_value=False
    )
    @patch("groups.tasks.logger")
    def test_other_discord_role_errors_still_error(
        self, mock_logger, mock_handle, mock_primary
    ):
        mock_primary.return_value = MagicMock()
        exc = DiscordRoleAssignmentError(
            "Cannot add user 1 to group X: no DiscordUser"
        )
        log_affiliation_update_error(self.user, exc)
        mock_logger.error.assert_called()
        self.assertTrue(mock_handle.called)
