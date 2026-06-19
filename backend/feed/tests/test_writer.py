from __future__ import annotations

from django.test import TestCase
from django.utils import timezone

from feed.models import FeedEvent
from feed.rollups.types import RollupResult
from feed.rollups.writer import write_rollup_results


class WriterTestCase(TestCase):
    def test_write_rollup_results_updates_existing_event(self):
        cluster_key = "fleet_active:30002542:500002:2026-06-19T20:00"
        write_rollup_results(
            [
                RollupResult(
                    kind=FeedEvent.Kind.FLEET_ACTIVE,
                    occurred_at=timezone.now(),
                    title="Minmatar fleet active",
                    subheader="Auga · 8 kills · 10 pilots",
                    preview="Active on front lines.",
                    body="",
                    accent=FeedEvent.Accent.MILITIA,
                    payload={"system_id": 30002542},
                    rollup_code="fleet_active",
                    rollup_version=1,
                    cluster_key=cluster_key,
                )
            ]
        )
        write_rollup_results(
            [
                RollupResult(
                    kind=FeedEvent.Kind.FLEET_ACTIVE,
                    occurred_at=timezone.now(),
                    title="Minmatar fleet active",
                    subheader="Auga · 12 kills · 14 pilots",
                    preview="Heavy fighting.",
                    body="",
                    accent=FeedEvent.Accent.MILITIA,
                    payload={"system_id": 30002542, "kills": 12},
                    rollup_code="fleet_active",
                    rollup_version=1,
                    cluster_key=cluster_key,
                )
            ]
        )

        events = FeedEvent.objects.filter(
            rollup_code="fleet_active",
            cluster_key=cluster_key,
        )
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.get().subheader, "Auga · 12 kills · 14 pilots")
