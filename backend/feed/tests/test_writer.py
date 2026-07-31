from __future__ import annotations

from django.test import TestCase
from django.utils import timezone

from feed.models import FeedEvent, FeedEventKillmailLink, FeedKillmail
from feed.rollups.types import RollupResult
from feed.rollups.writer import (
    _apply_upgrade_metadata,
    _sync_killmail_links,
    write_rollup_results,
)


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

    def test_write_coalesces_duplicate_fleet_active_events(self):
        now = timezone.now()
        related = "fleet_engagement:30002542:500002:2026-06-19T20:00"
        # Two pre-existing duplicate cards for the same engagement, keyed
        # differently (the old bug).
        for start in ("2026-06-19T20:00", "2026-06-19T20:05"):
            FeedEvent.objects.create(
                kind=FeedEvent.Kind.FLEET_ACTIVE,
                rollup_code="fleet_active",
                cluster_key=f"fleet_active:30002542:500002:{start}",
                occurred_at=now,
                title="Medium Minmatar gang active",
                subheader="",
                preview="",
                body="",
                accent=FeedEvent.Accent.MILITIA,
                payload={
                    "system_id": 30002542,
                    "faction": "minmatar",
                    "related_cluster_key": related,
                    "engagement_tier": "medium",
                    "kills": 14,
                    "pilots": 12,
                },
                rollup_version=1,
            )
        self.assertEqual(
            FeedEvent.objects.filter(rollup_code="fleet_active").count(), 2
        )

        write_rollup_results(
            [
                RollupResult(
                    kind=FeedEvent.Kind.FLEET_ACTIVE,
                    occurred_at=now,
                    title="Major Minmatar fleet active",
                    subheader="",
                    preview="",
                    body="",
                    accent=FeedEvent.Accent.MILITIA,
                    payload={
                        "system_id": 30002542,
                        "faction": "minmatar",
                        "related_cluster_key": related,
                        "engagement_tier": "major",
                        "kills": 60,
                        "pilots": 45,
                    },
                    rollup_code="fleet_active",
                    rollup_version=1,
                    cluster_key="fleet_active:30002542:500002:2026-06-19T20:00",
                )
            ]
        )

        events = FeedEvent.objects.filter(rollup_code="fleet_active")
        self.assertEqual(events.count(), 1)
        event = events.get()
        self.assertEqual(event.payload.get("engagement_tier"), "major")
        self.assertEqual(event.payload.get("previous_tier"), "medium")
        self.assertIsNotNone(event.payload.get("upgraded_at"))

    def test_write_keeps_distinct_fleet_active_events_apart(self):
        now = timezone.now()
        # A different system/faction engagement must not be coalesced.
        FeedEvent.objects.create(
            kind=FeedEvent.Kind.FLEET_ACTIVE,
            rollup_code="fleet_active",
            cluster_key="fleet_active:30002539:500003:2026-06-19T20:00",
            occurred_at=now,
            title="Medium Amarr gang active",
            subheader="",
            preview="",
            body="",
            accent=FeedEvent.Accent.AMARR,
            payload={
                "system_id": 30002539,
                "faction": "amarr",
                "related_cluster_key": "fleet_engagement:30002539:500003:x",
                "engagement_tier": "medium",
            },
            rollup_version=1,
        )

        write_rollup_results(
            [
                RollupResult(
                    kind=FeedEvent.Kind.FLEET_ACTIVE,
                    occurred_at=now,
                    title="Medium Minmatar gang active",
                    subheader="",
                    preview="",
                    body="",
                    accent=FeedEvent.Accent.MILITIA,
                    payload={
                        "system_id": 30002542,
                        "faction": "minmatar",
                        "related_cluster_key": "fleet_engagement:30002542:500002:y",
                        "engagement_tier": "medium",
                    },
                    rollup_code="fleet_active",
                    rollup_version=1,
                    cluster_key="fleet_active:30002542:500002:2026-06-19T20:00",
                )
            ]
        )

        self.assertEqual(
            FeedEvent.objects.filter(rollup_code="fleet_active").count(), 2
        )

    def test_sync_killmail_links_is_idempotent(self):
        event = FeedEvent.objects.create(
            kind=FeedEvent.Kind.FLEET_ACTIVE,
            rollup_code="fleet_active",
            cluster_key="fleet_active:30002542:500002:idempotent",
            occurred_at=timezone.now(),
            title="Fleet",
            subheader="",
            preview="",
            body="",
            accent=FeedEvent.Accent.MILITIA,
            payload={},
            rollup_version=1,
        )
        km = FeedKillmail.objects.create(
            killmail_id=137371129,
            hash="abc",
            killmail_time=timezone.now(),
            solar_system_id=30002542,
            raw_killmail={},
        )
        _sync_killmail_links(event, [km.killmail_id])
        _sync_killmail_links(event, [km.killmail_id])
        # Concurrent create path: existing link + bulk_create ignore_conflicts
        FeedEventKillmailLink.objects.bulk_create(
            [FeedEventKillmailLink(feed_event=event, feed_killmail=km)],
            ignore_conflicts=True,
        )
        self.assertEqual(
            FeedEventKillmailLink.objects.filter(feed_event=event).count(), 1
        )

    def test_apply_upgrade_metadata_tolerates_deleted_event(self):
        event = FeedEvent.objects.create(
            kind=FeedEvent.Kind.FLEET_ACTIVE,
            rollup_code="fleet_active",
            cluster_key="fleet_active:30002542:500002:deleted",
            occurred_at=timezone.now(),
            title="Major fleet",
            subheader="",
            preview="",
            body="",
            accent=FeedEvent.Accent.MILITIA,
            payload={"engagement_tier": "major", "kills": 60, "pilots": 40},
            rollup_version=1,
        )
        prior = [{"engagement_tier": "medium", "kills": 14, "pilots": 12}]
        event_pk = event.pk
        FeedEvent.objects.filter(pk=event_pk).delete()
        # Must not raise DatabaseError when the row was concurrently deleted.
        _apply_upgrade_metadata(event, prior)
        self.assertFalse(FeedEvent.objects.filter(pk=event_pk).exists())
