from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from feed.helpers.clusters import detect_clusters
from feed.helpers.zkill_backfill import (
    ZKILL_MAX_PAST_SECONDS,
    backfill_monitored_systems,
)
from feed.tasks import run_feed_rollups


class Command(BaseCommand):
    help = (
        "Backfill FeedKillmail rows from zKill for all monitored systems "
        "over the last N hours"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="How far back to pull kills (max 168 / 7 days)",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=0.25,
            help="Seconds to sleep between ESI killmail fetches",
        )
        parser.add_argument(
            "--rebuild",
            action="store_true",
            help="Run cluster detection and feed rollups after backfill",
        )
        parser.add_argument(
            "--rebuild-hours",
            dest="rebuild_hours",
            type=int,
            default=None,
            help="Lookback for rebuild step (defaults to --hours)",
        )

    def handle(self, *args, **options):
        hours = options["hours"]
        max_hours = ZKILL_MAX_PAST_SECONDS // 3600
        if hours < 1 or hours > max_hours:
            raise CommandError(f"--hours must be between 1 and {max_hours}")

        try:
            stats = backfill_monitored_systems(
                hours=hours,
                sleep_seconds=options["sleep"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(str(stats))

        if options["rebuild"]:
            rebuild_hours = options["rebuild_hours"] or hours
            cluster_count = detect_clusters(since_hours=rebuild_hours)
            rollup_count = run_feed_rollups(since_hours=rebuild_hours)
            self.stdout.write(f"Updated {cluster_count} clusters")
            self.stdout.write(
                self.style.SUCCESS(
                    f"Rebuild complete: {cluster_count} clusters, "
                    f"{rollup_count} rollup events"
                )
            )
