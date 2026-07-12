from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from feed.helpers.r2z2 import poll_r2z2_batch
from feed.management.commands.seed_feed_monitored_systems import (
    seed_from_fixture,
)
from feed.models import FeedKillmail, FeedR2z2Cursor
from feed.tests.helpers import make_killmail_payload


class R2z2PollTestCase(TestCase):
    def setUp(self):
        seed_from_fixture()

    @patch("feed.helpers.r2z2.fetch_sequence_payload")
    @patch("feed.helpers.r2z2.fetch_latest_sequence")
    def test_poll_inserts_monitored_kill(self, mock_latest, mock_fetch):
        mock_latest.return_value = 100
        payload = make_killmail_payload(136398967)
        mock_fetch.side_effect = [(200, payload, None), (404, None, None)]

        stats = poll_r2z2_batch(max_seconds=1)

        self.assertEqual(stats["inserted"], 1)
        self.assertEqual(FeedKillmail.objects.count(), 1)
        cursor = FeedR2z2Cursor.get_singleton()
        self.assertEqual(cursor.last_sequence_id, 100)

    @patch("feed.helpers.r2z2.time.sleep")
    @patch("feed.helpers.r2z2.fetch_sequence_payload")
    def test_poll_rate_limited_backs_off_without_advancing_cursor(
        self, mock_fetch, mock_sleep
    ):
        FeedR2z2Cursor.objects.create(pk=1, last_sequence_id=99)
        mock_fetch.return_value = (429, None, 120.0)

        stats = poll_r2z2_batch(max_seconds=1)

        self.assertEqual(
            stats,
            {
                "processed": 0,
                "inserted": 0,
                "discarded": 0,
                "errors": 0,
                "rate_limited": 1,
                "banned": 0,
            },
        )
        mock_sleep.assert_called_once_with(120.0)
        cursor = FeedR2z2Cursor.get_singleton()
        self.assertEqual(cursor.last_sequence_id, 99)

    @patch("feed.helpers.r2z2.time.sleep")
    @patch("feed.helpers.r2z2.fetch_sequence_payload")
    def test_poll_forbidden_backs_off_without_advancing_cursor(
        self, mock_fetch, mock_sleep
    ):
        FeedR2z2Cursor.objects.create(pk=1, last_sequence_id=99)
        mock_fetch.return_value = (403, None, 3600.0)

        stats = poll_r2z2_batch(max_seconds=1)

        self.assertEqual(
            stats,
            {
                "processed": 0,
                "inserted": 0,
                "discarded": 0,
                "errors": 0,
                "rate_limited": 0,
                "banned": 1,
            },
        )
        mock_sleep.assert_called_once_with(3600.0)
        cursor = FeedR2z2Cursor.get_singleton()
        self.assertEqual(cursor.last_sequence_id, 99)
