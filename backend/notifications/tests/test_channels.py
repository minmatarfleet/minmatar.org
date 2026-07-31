from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings

from discord.models import DiscordUser
from notifications.channels import ChannelSendError, ChannelSkip, send_channel
from notifications.models import NotificationChannel
from notifications.rate_limit import acquire


class RateLimitTestCase(SimpleTestCase):
    @override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "notif-rate-tests",
            }
        }
    )
    def test_locmem_acquire_throttles(self):
        allowed, unused_retry = acquire(
            "test_bucket_a", rate_per_second=1.0, capacity=1.0, tokens=1.0
        )
        del unused_retry
        self.assertTrue(allowed)
        allowed, retry = acquire(
            "test_bucket_a", rate_per_second=1.0, capacity=1.0, tokens=1.0
        )
        self.assertFalse(allowed)
        self.assertGreater(retry, 0)

    def test_redis_eval_failure_fails_closed(self):
        mock_client = MagicMock()
        mock_client.get_client.return_value.eval.side_effect = RuntimeError(
            "redis down"
        )
        with patch("notifications.rate_limit.cache") as mock_cache:
            mock_cache.client = mock_client
            allowed, retry = acquire(
                "test_bucket_b",
                rate_per_second=2.0,
                capacity=2.0,
                tokens=1.0,
            )
        self.assertFalse(allowed)
        self.assertGreaterEqual(retry, 0.5)


class DiscordChannelErrorTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("dmuser", password="x")
        DiscordUser.objects.create(
            id=555666777,
            discord_tag="dmuser#0001",
            user=self.user,
        )

    @patch("notifications.channels.acquire", return_value=(True, 0.0))
    @patch("notifications.channels.DiscordClient")
    def test_discord_403_is_skip(self, mock_client_cls, mock_acquire):
        del mock_acquire
        response = MagicMock()
        response.status_code = 403
        err = requests.HTTPError(response=response)
        err.response = response
        mock_client_cls.return_value.send_dm.side_effect = err
        with self.assertRaises(ChannelSkip):
            send_channel(
                NotificationChannel.DISCORD,
                self.user,
                {"discord_message": "hi", "feature": "industry"},
            )

    @patch("notifications.channels.acquire", return_value=(True, 0.0))
    @patch("notifications.channels.DiscordClient")
    def test_discord_400_is_not_retryable(self, mock_client_cls, mock_acquire):
        del mock_acquire
        response = MagicMock()
        response.status_code = 400
        err = requests.HTTPError(response=response)
        err.response = response
        mock_client_cls.return_value.send_dm.side_effect = err
        with self.assertRaises(ChannelSendError) as ctx:
            send_channel(
                NotificationChannel.DISCORD,
                self.user,
                {"discord_message": "hi", "feature": "industry"},
            )
        self.assertFalse(ctx.exception.retryable)
