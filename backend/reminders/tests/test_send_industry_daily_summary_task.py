"""Celery task: post industry summary to Discord."""

from unittest.mock import MagicMock, patch

from django.test import override_settings

from app.test import TestCase as AppTestCase
from reminders.tasks import send_industry_daily_summary


class SendIndustryDailySummaryTaskTests(AppTestCase):
    @patch("reminders.tasks.DiscordClient")
    @override_settings(DISCORD_INDUSTRY_CHANNEL_ID=555001)
    def test_posts_message_when_channel_configured(self, mock_dc):
        mock_dc.return_value.create_message = MagicMock()
        send_industry_daily_summary()
        mock_dc.return_value.create_message.assert_called_once()
        call = mock_dc.return_value.create_message.call_args
        self.assertEqual(call.args[0], 555001)
        self.assertIn("# Industry order summary", call.args[1])

    @patch("reminders.tasks.DiscordClient")
    @override_settings(DISCORD_INDUSTRY_CHANNEL_ID=0)
    def test_skips_when_channel_unset(self, mock_dc):
        send_industry_daily_summary()
        mock_dc.return_value.create_message.assert_not_called()
