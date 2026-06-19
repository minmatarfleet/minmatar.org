from __future__ import annotations

from django.test import TestCase

from feed.helpers.ingest import upsert_feed_killmail_from_r2z2
from feed.helpers.killmail_classify import is_npc_kill
from feed.management.commands.seed_feed_monitored_systems import (
    seed_from_fixture,
)
from feed.models import FeedKillmail
from feed.tests.helpers import jita_killmail_payload, make_killmail_payload


class IngestTestCase(TestCase):
    def setUp(self):
        seed_from_fixture()

    def test_ingest_monitored_system_killmail(self):
        payload = make_killmail_payload(136398967)
        result = upsert_feed_killmail_from_r2z2(payload)
        self.assertIsNotNone(result)
        self.assertEqual(FeedKillmail.objects.count(), 1)

    def test_discard_jita_killmail(self):
        payload = jita_killmail_payload()
        result = upsert_feed_killmail_from_r2z2(payload)
        self.assertIsNone(result)
        self.assertEqual(FeedKillmail.objects.count(), 0)

    def test_discard_npc_killmail(self):
        payload = make_killmail_payload(123)
        payload["zkb"]["npc"] = True
        result = upsert_feed_killmail_from_r2z2(payload)
        self.assertIsNone(result)

    def test_dedup_by_killmail_id(self):
        payload = make_killmail_payload(136398967)
        upsert_feed_killmail_from_r2z2(payload)
        upsert_feed_killmail_from_r2z2(payload)
        self.assertEqual(FeedKillmail.objects.count(), 1)

    def test_is_npc_kill(self):
        self.assertTrue(is_npc_kill({"npc": True}))
        self.assertFalse(is_npc_kill({"npc": False}))
