from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase
from django.utils import timezone

from feed.helpers.r2z2 import poll_r2z2_batch
from feed.management.commands.seed_feed_monitored_systems import (
    seed_from_fixture,
)
from feed.models import FeedKillmail, FeedR2z2Cursor
from feed.tests.helpers import make_killmail_payload


class R2z2PollTestCase(TestCase):
    def setUp(self):
        seed_from_fixture()

    @patch("feed.helpers.r2z2.maybe_notify_capital_kill")
    @patch("feed.helpers.r2z2.fetch_sequence_payload")
    @patch("feed.helpers.r2z2.fetch_latest_sequence")
    def test_poll_inserts_monitored_kill(
        self, mock_latest, mock_fetch, mock_ping
    ):
        mock_ping.return_value = False
        mock_latest.return_value = 100
        payload = make_killmail_payload(136398967)
        mock_fetch.side_effect = [(200, payload, None), (404, None, None)]

        stats = poll_r2z2_batch(max_seconds=5)

        self.assertEqual(stats["inserted"], 1)
        self.assertEqual(stats["live_processed"], 1)
        self.assertEqual(FeedKillmail.objects.count(), 1)
        cursor = FeedR2z2Cursor.get_singleton()
        self.assertEqual(cursor.live_sequence_id, 100)
        self.assertEqual(cursor.last_sequence_id, 100)

    @patch("feed.helpers.r2z2.maybe_notify_capital_kill")
    @patch("feed.helpers.r2z2.time.sleep")
    @patch("feed.helpers.r2z2.fetch_sequence_payload")
    def test_poll_rate_limited_sets_paused_without_long_sleep(
        self, mock_fetch, mock_sleep, mock_ping
    ):
        mock_ping.return_value = False
        FeedR2z2Cursor.objects.create(
            pk=1,
            last_sequence_id=99,
            live_sequence_id=99,
            catchup_sequence_id=99,
        )
        mock_fetch.return_value = (429, None, 120.0)

        stats = poll_r2z2_batch(max_seconds=5)

        self.assertEqual(stats["outcome"], "rate_limited")
        self.assertEqual(stats["rate_limited"], 1)
        self.assertEqual(stats["live_processed"], 0)
        long_sleeps = [
            call
            for call in mock_sleep.call_args_list
            if call.args and call.args[0] >= 60
        ]
        self.assertEqual(long_sleeps, [])
        cursor = FeedR2z2Cursor.get_singleton()
        self.assertEqual(cursor.live_sequence_id, 99)
        self.assertIsNotNone(cursor.paused_until)
        self.assertGreater(cursor.paused_until, timezone.now())

    @patch("feed.helpers.r2z2.maybe_notify_capital_kill")
    @patch("feed.helpers.r2z2.time.sleep")
    @patch("feed.helpers.r2z2.fetch_sequence_payload")
    def test_poll_forbidden_sets_paused_without_long_sleep(
        self, mock_fetch, mock_sleep, mock_ping
    ):
        mock_ping.return_value = False
        FeedR2z2Cursor.objects.create(
            pk=1,
            last_sequence_id=99,
            live_sequence_id=99,
            catchup_sequence_id=99,
        )
        mock_fetch.return_value = (403, None, 3600.0)

        stats = poll_r2z2_batch(max_seconds=5)

        self.assertEqual(stats["outcome"], "banned")
        self.assertEqual(stats["banned"], 1)
        long_sleeps = [
            call
            for call in mock_sleep.call_args_list
            if call.args and call.args[0] >= 60
        ]
        self.assertEqual(long_sleeps, [])
        cursor = FeedR2z2Cursor.get_singleton()
        self.assertEqual(cursor.live_sequence_id, 99)
        self.assertIsNotNone(cursor.paused_until)

    @patch("feed.helpers.r2z2.fetch_sequence_payload")
    def test_poll_skipped_while_paused(self, mock_fetch):
        FeedR2z2Cursor.objects.create(
            pk=1,
            live_sequence_id=99,
            catchup_sequence_id=50,
            last_sequence_id=99,
            paused_until=timezone.now() + timedelta(hours=1),
        )

        stats = poll_r2z2_batch(max_seconds=5)

        self.assertEqual(stats["outcome"], "skipped_paused")
        mock_fetch.assert_not_called()

    @patch("feed.helpers.r2z2.maybe_notify_capital_kill")
    @patch("feed.helpers.r2z2.fetch_sequence_payload")
    @patch("feed.helpers.r2z2.fetch_latest_sequence")
    def test_live_before_catchup_after_tip(
        self, mock_latest, mock_fetch, mock_ping
    ):
        mock_ping.return_value = False
        mock_latest.return_value = 110
        FeedR2z2Cursor.objects.create(
            pk=1,
            live_sequence_id=109,
            catchup_sequence_id=100,
            last_sequence_id=109,
            live_idle_until=timezone.now() + timedelta(seconds=30),
        )
        live_payload = make_killmail_payload(1)
        catchup_payload = make_killmail_payload(2)
        mock_fetch.side_effect = [
            (200, live_payload, None),
            (404, None, None),
            (200, catchup_payload, None),
            (404, None, None),
        ]

        stats = poll_r2z2_batch(max_seconds=5)

        self.assertEqual(stats["live_processed"], 1)
        self.assertGreaterEqual(stats["catchup_processed"], 1)
        cursor = FeedR2z2Cursor.get_singleton()
        self.assertEqual(cursor.live_sequence_id, 110)
        self.assertGreaterEqual(cursor.catchup_sequence_id, 101)

    @patch("feed.helpers.r2z2.maybe_notify_capital_kill")
    @patch("feed.helpers.r2z2.fetch_sequence_payload")
    def test_no_catchup_when_live_still_bursting(self, mock_fetch, mock_ping):
        mock_ping.return_value = False
        FeedR2z2Cursor.objects.create(
            pk=1,
            live_sequence_id=100,
            catchup_sequence_id=50,
            last_sequence_id=100,
        )
        payload = make_killmail_payload(1)
        # Live keeps returning 200 until budget exhausted — never tips.
        mock_fetch.return_value = (200, payload, None)

        stats = poll_r2z2_batch(max_seconds=0.35)

        self.assertGreaterEqual(stats["live_processed"], 1)
        self.assertEqual(stats["catchup_processed"], 0)

    @patch("feed.helpers.r2z2._lock_cursor")
    def test_skipped_locked_on_lock_contention(self, mock_lock):
        mock_lock.side_effect = OperationalError("database is locked")

        stats = poll_r2z2_batch(max_seconds=1)

        self.assertEqual(stats["outcome"], "skipped_locked")

    @patch("feed.helpers.r2z2.maybe_notify_capital_kill")
    @patch("feed.helpers.r2z2.time.sleep")
    @patch("feed.helpers.r2z2.fetch_sequence_payload")
    def test_retry_after_uses_header_not_max_with_default(
        self, mock_fetch, mock_sleep, mock_ping
    ):
        mock_ping.return_value = False
        FeedR2z2Cursor.objects.create(
            pk=1,
            live_sequence_id=99,
            catchup_sequence_id=99,
            last_sequence_id=99,
        )
        mock_fetch.return_value = (429, None, 30.0)

        poll_r2z2_batch(max_seconds=5)

        cursor = FeedR2z2Cursor.get_singleton()
        remaining = (cursor.paused_until - timezone.now()).total_seconds()
        self.assertLess(remaining, 120)
        self.assertGreater(remaining, 0)
