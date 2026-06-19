from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from feed.management.commands.seed_feed_monitored_systems import (
    seed_from_fixture,
)
from feed.models import FeedEvent, FeedMilitiaFirstSeen
from feed.rollups.registry import build_context, run_rollup
from feed.rollups.writer import write_rollup_results


class MilitiaRollupTestCase(TestCase):
    def setUp(self):
        seed_from_fixture()
        now = timezone.now()
        for i in range(6):
            FeedMilitiaFirstSeen.objects.create(
                character_id=700000 + i,
                faction_id=500002,
                first_seen_at=now - timedelta(minutes=30),
                first_seen_killmail_id=1000 + i,
                role="attacker",
                solar_system_id=30002538,
            )

    def test_militia_hourly_rollup(self):
        now = timezone.now()
        ctx = build_context(now - timedelta(hours=2), now)
        results = run_rollup("militia_joins", ctx)
        self.assertTrue(
            any(r.kind == FeedEvent.Kind.MILITIA_JOINS for r in results)
        )
        hourly = [r for r in results if r.payload.get("window_hours") == 1]
        self.assertTrue(hourly)
        self.assertIn("newly active", hourly[0].title)
        write_rollup_results(hourly[:1])
        self.assertEqual(
            FeedEvent.objects.filter(
                kind=FeedEvent.Kind.MILITIA_JOINS
            ).count(),
            1,
        )
