from __future__ import annotations

from django.core.management.base import BaseCommand

from feed.helpers.clusters import detect_clusters
from feed.tasks import run_feed_rollups


class Command(BaseCommand):
    help = "Re-detect FeedCluster rows from FeedKillmail facts"

    def add_arguments(self, parser):
        parser.add_argument(
            "--since", dest="since_hours", type=int, default=48
        )
        parser.add_argument(
            "--rebuild-rollups",
            action="store_true",
            help="Also run rebuild_feed_rollups after cluster detection",
        )

    def handle(self, *args, **options):
        count = detect_clusters(since_hours=options["since_hours"])
        self.stdout.write(f"Updated {count} clusters")
        if options["rebuild_rollups"]:
            written = run_feed_rollups(since_hours=options["since_hours"])
            self.stdout.write(f"Rebuilt {written} rollup events")
