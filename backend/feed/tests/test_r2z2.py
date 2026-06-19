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
        mock_fetch.side_effect = [(200, payload), (404, None)]

        stats = poll_r2z2_batch(max_seconds=1)

        self.assertEqual(stats["inserted"], 1)
        self.assertEqual(FeedKillmail.objects.count(), 1)
        cursor = FeedR2z2Cursor.get_singleton()
        self.assertEqual(cursor.last_sequence_id, 100)
