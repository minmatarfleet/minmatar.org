from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.test import override_settings

from alliance.helpers.health import latest_snapshot, snapshot_before
from alliance.helpers.snapshot_retention import (
    KEEP_ALL_DAYS,
    prune_alliance_health_snapshots,
)
from alliance.models import AllianceHealthSnapshot
from alliance.tasks import prune_alliance_health_snapshots_task
from app.test import TestCase

NOW = datetime(2026, 10, 17, 12, 25, tzinfo=dt_timezone.utc)


class SnapshotRetentionTestCase(TestCase):
    def setUp(self):
        super().setUp()
        # Hourly snapshots for 60 days, as the beat task writes them.
        AllianceHealthSnapshot.objects.bulk_create(
            AllianceHealthSnapshot(
                computed_at=NOW - timedelta(hours=h), payload={"h": h}
            )
            for h in range(60 * 24)
        )
        self.before_count = AllianceHealthSnapshot.objects.count()

    def _prune(self, **kwargs):
        with patch("django.utils.timezone.now", return_value=NOW):
            return prune_alliance_health_snapshots(**kwargs)

    def test_current_readers_see_the_same_rows(self):
        latest = latest_snapshot()
        prior = snapshot_before(latest.computed_at - timedelta(days=30))
        self._prune()
        self.assertEqual(latest_snapshot().pk, latest.pk)
        self.assertEqual(
            snapshot_before(latest.computed_at - timedelta(days=30)).pk,
            prior.pk,
        )

    def test_keeps_the_window_hourly_and_one_per_day_before_it(self):
        deleted = self._prune()
        cutoff = NOW - timedelta(days=KEEP_ALL_DAYS)
        recent = AllianceHealthSnapshot.objects.filter(computed_at__gte=cutoff)
        old = AllianceHealthSnapshot.objects.filter(computed_at__lt=cutoff)
        # Hourly rows back to and including the cutoff hour.
        self.assertEqual(recent.count(), KEEP_ALL_DAYS * 24 + 1)
        days = [s.computed_at.date() for s in old]
        self.assertEqual(len(days), len(set(days)))
        # Each kept old row is the last one written that day (the cutoff
        # day's last row before the cutoff stays too).
        for snap in old:
            if snap.computed_at.date() != cutoff.date():
                self.assertEqual(snap.computed_at.hour, 23)
        self.assertEqual(
            deleted, self.before_count - recent.count() - len(days)
        )

    def test_dry_run_deletes_nothing(self):
        would = self._prune(dry_run=True)
        self.assertGreater(would, 0)
        self.assertEqual(
            AllianceHealthSnapshot.objects.count(), self.before_count
        )

    def test_second_run_is_a_no_op(self):
        self._prune()
        self.assertEqual(self._prune(), 0)

    @override_settings(ALLIANCE_HEALTH_SNAPSHOT_PRUNE_ENABLED=True)
    def test_task_runs_the_prune(self):
        with patch("django.utils.timezone.now", return_value=NOW):
            deleted = prune_alliance_health_snapshots_task()
        self.assertGreater(deleted, 0)

    def test_task_deletes_nothing_by_default(self):
        with patch("django.utils.timezone.now", return_value=NOW):
            deleted = prune_alliance_health_snapshots_task()
        self.assertEqual(deleted, 0)
        self.assertEqual(
            AllianceHealthSnapshot.objects.count(), self.before_count
        )

    def test_task_dry_run_counts_while_disabled(self):
        with patch("django.utils.timezone.now", return_value=NOW):
            would = prune_alliance_health_snapshots_task(dry_run=True)
        self.assertGreater(would, 0)
        self.assertEqual(
            AllianceHealthSnapshot.objects.count(), self.before_count
        )
