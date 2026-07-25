from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from feed.constants import FACTION_CALDARI, FACTION_MINMATAR
from feed.helpers.ingest import upsert_feed_killmail_from_r2z2
from feed.helpers.monitored_systems import (
    invalidate_monitored_systems_cache,
)
from feed.management.commands.seed_feed_monitored_systems import (
    seed_from_fixture,
)
from feed.models import FeedCluster, FeedEvent
from feed.rollups.fleet_active import (
    _collapse_fleet_clusters,
    run_fleet_active_rollup,
)
from feed.rollups.registry import build_context
from feed.rollups.writer import write_rollup_results
from feed.tests.helpers import make_killmail_payload


class FleetActiveRollupTestCase(TestCase):
    def setUp(self):
        seed_from_fixture()
        invalidate_monitored_systems_cache()

    def test_collapse_fleet_clusters_merges_adjacent_buckets(self):
        base = timezone.now()
        clusters = [
            FeedCluster(
                cluster_key=f"fleet_engagement:30002542:500002:2026-06-19T20:{minute:02d}",
                cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT,
                solar_system_id=30002542,
                dominant_faction_id=500002,
                started_at=base + timedelta(minutes=minute),
                last_kill_at=base + timedelta(minutes=minute + 15),
                kill_count=8,
                pilot_count=10,
            )
            for minute in (0, 20, 40)
        ]

        collapsed = _collapse_fleet_clusters(clusters)

        self.assertEqual(len(collapsed), 1)
        chain = collapsed[0]
        self.assertEqual(len(chain), 3)
        # Chain is ordered by started_at: earliest is canonical, last carries
        # the most recent kill.
        self.assertEqual(chain[0][0].started_at, clusters[0].started_at)
        self.assertEqual(chain[-1][0].last_kill_at, clusters[-1].last_kill_at)

    def test_collapse_fleet_clusters_keeps_separate_engagements(self):
        base = timezone.now()
        first = FeedCluster(
            cluster_key="fleet_engagement:30002542:500002:2026-06-19T10:00",
            cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT,
            solar_system_id=30002542,
            dominant_faction_id=500002,
            started_at=base,
            last_kill_at=base + timedelta(minutes=15),
            kill_count=8,
            pilot_count=10,
        )
        second = FeedCluster(
            cluster_key="fleet_engagement:30002542:500002:2026-06-19T14:00",
            cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT,
            solar_system_id=30002542,
            dominant_faction_id=500002,
            started_at=base + timedelta(hours=4),
            last_kill_at=base + timedelta(hours=4, minutes=15),
            kill_count=6,
            pilot_count=9,
        )

        collapsed = _collapse_fleet_clusters([first, second])

        self.assertEqual(len(collapsed), 2)

    def test_rollup_ignores_stale_cluster_dominant_faction(self):
        base = timezone.now()
        killmail_ids = []
        for i in range(3):
            payload = make_killmail_payload(
                88000000 + i,
                killmail_time=base,
                attacker_count=0,
            )
            raw = payload["killmail"]
            raw["attackers"] = [
                {
                    "character_id": 90000000 + j,
                    "corporation_id": 98000000,
                    "alliance_id": 99000000,
                    "faction_id": 500002,
                    "ship_type_id": 22468,
                    "damage_done": 1000,
                    "final_blow": j == 0,
                }
                for j in range(2)
            ] + [
                {
                    "character_id": 91000000 + j,
                    "corporation_id": 98000000,
                    "alliance_id": 99000000,
                    "faction_id": FACTION_CALDARI,
                    "ship_type_id": 22468,
                    "damage_done": 1000,
                    "final_blow": False,
                }
                for j in range(8)
            ]
            upsert_feed_killmail_from_r2z2(payload)
            killmail_ids.append(88000000 + i)

        FeedCluster.objects.create(
            cluster_key="fleet_engagement:30002542:500002:2026-06-19T20:00",
            cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT,
            solar_system_id=30002542,
            dominant_faction_id=500002,
            started_at=base,
            last_kill_at=base,
            kill_count=3,
            pilot_count=10,
            killmail_ids=killmail_ids,
        )

        ctx = build_context(
            base - timedelta(hours=1), base + timedelta(hours=1)
        )
        results = run_fleet_active_rollup(ctx)

        self.assertEqual(len(results), 0)

    def _make_fleet_cluster(
        self,
        *,
        killmail_ids,
        started_at,
        last_kill_at,
        kill_count,
        pilot_count,
        faction_id=FACTION_MINMATAR,
        is_active=True,
        solar_system_id=30002538,
        key_suffix="",
    ):
        started_label = started_at.strftime("%Y-%m-%dT%H:%M")
        return FeedCluster.objects.create(
            cluster_key=(
                f"fleet_engagement:{solar_system_id}:{faction_id}:"
                f"{started_label}{key_suffix}"
            ),
            cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT,
            solar_system_id=solar_system_id,
            dominant_faction_id=faction_id,
            started_at=started_at,
            last_kill_at=last_kill_at,
            kill_count=kill_count,
            pilot_count=pilot_count,
            killmail_ids=killmail_ids,
            is_active=is_active,
        )

    def _seed_killmails(self, start_id, count, base_time):
        ids = []
        for i in range(count):
            km_id = start_id + i
            upsert_feed_killmail_from_r2z2(
                make_killmail_payload(
                    km_id, killmail_time=base_time + timedelta(minutes=i)
                )
            )
            ids.append(km_id)
        return ids

    def test_growing_fight_updates_single_event_with_upgrade_marker(self):
        base = timezone.now() - timedelta(minutes=30)
        killmail_ids = self._seed_killmails(87000000, 6, base)
        cluster = self._make_fleet_cluster(
            killmail_ids=killmail_ids,
            started_at=base,
            last_kill_at=base + timedelta(minutes=5),
            kill_count=14,
            pilot_count=12,
        )

        now = timezone.now()
        ctx = build_context(now - timedelta(hours=1), now + timedelta(hours=1))
        write_rollup_results(run_fleet_active_rollup(ctx))

        events = FeedEvent.objects.filter(kind=FeedEvent.Kind.FLEET_ACTIVE)
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.get().payload.get("engagement_tier"), "medium")

        # Same fight grows to a major engagement on the same cluster.
        cluster.kill_count = 60
        cluster.pilot_count = 45
        cluster.last_kill_at = base + timedelta(minutes=12)
        cluster.save()

        write_rollup_results(run_fleet_active_rollup(ctx))

        events = FeedEvent.objects.filter(kind=FeedEvent.Kind.FLEET_ACTIVE)
        self.assertEqual(events.count(), 1)
        event = events.get()
        self.assertEqual(event.payload.get("engagement_tier"), "major")
        self.assertEqual(event.payload.get("previous_tier"), "medium")
        self.assertIsNotNone(event.payload.get("upgraded_at"))

    def test_adjacent_clusters_collapse_to_single_cluster_and_event(self):
        base = timezone.now() - timedelta(minutes=40)
        ids_a = self._seed_killmails(85000000, 4, base)
        ids_b = self._seed_killmails(85000100, 4, base + timedelta(minutes=10))
        self._make_fleet_cluster(
            killmail_ids=ids_a,
            started_at=base,
            last_kill_at=base + timedelta(minutes=3),
            kill_count=8,
            pilot_count=8,
        )
        self._make_fleet_cluster(
            killmail_ids=ids_b,
            started_at=base + timedelta(minutes=10),
            last_kill_at=base + timedelta(minutes=13),
            kill_count=8,
            pilot_count=8,
        )

        now = timezone.now()
        ctx = build_context(now - timedelta(hours=1), now + timedelta(hours=1))
        write_rollup_results(run_fleet_active_rollup(ctx))

        self.assertEqual(
            FeedCluster.objects.filter(
                cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT
            ).count(),
            1,
        )
        self.assertEqual(
            FeedEvent.objects.filter(kind=FeedEvent.Kind.FLEET_ACTIVE).count(),
            1,
        )

    def test_separate_engagements_stay_distinct(self):
        base = timezone.now() - timedelta(hours=5)
        ids1 = self._seed_killmails(86000000, 6, base)
        self._make_fleet_cluster(
            killmail_ids=ids1,
            started_at=base,
            last_kill_at=base + timedelta(minutes=5),
            kill_count=14,
            pilot_count=12,
        )

        later = base + timedelta(hours=3)
        ids2 = self._seed_killmails(86000100, 6, later)
        self._make_fleet_cluster(
            killmail_ids=ids2,
            started_at=later,
            last_kill_at=later + timedelta(minutes=5),
            kill_count=14,
            pilot_count=12,
        )

        now = timezone.now()
        ctx = build_context(now - timedelta(hours=8), now + timedelta(hours=1))
        write_rollup_results(run_fleet_active_rollup(ctx))

        self.assertEqual(
            FeedEvent.objects.filter(kind=FeedEvent.Kind.FLEET_ACTIVE).count(),
            2,
        )
