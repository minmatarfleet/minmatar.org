from __future__ import annotations

from django.core.management import call_command
from django.test import TestCase

from feed.helpers.ingest import upsert_feed_killmail_from_r2z2
from feed.management.commands.seed_feed_monitored_systems import (
    seed_from_fixture,
)
from feed.models import FeedKillmail
from feed.tests.helpers import jita_killmail_payload, make_killmail_payload


class VerifyScopeTestCase(TestCase):
    def setUp(self):
        seed_from_fixture()
        upsert_feed_killmail_from_r2z2(make_killmail_payload(1001))

    def test_verify_feed_scope_passes(self):
        call_command("verify_feed_scope", sample_hours=24)

    def test_jita_not_in_feed(self):
        upsert_feed_killmail_from_r2z2(jita_killmail_payload())
        self.assertEqual(FeedKillmail.objects.count(), 1)
