from __future__ import annotations

from django.core.management.base import BaseCommand

from feed.helpers.clusters import detect_clusters
from feed.management.commands.rebuild_feed_rollups import (
    Command as RebuildRollupsCommand,
)
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
        parser.add_argument(
            "--wipe-rollups",
            action="store_true",
            help="Delete existing derived FeedEvent rows before rollup rebuild",
        )

    def handle(self, *args, **options):
        count = detect_clusters(since_hours=options["since_hours"])
        self.stdout.write(f"Updated {count} clusters")
        if options["rebuild_rollups"]:
            if options["wipe_rollups"]:
                RebuildRollupsCommand().handle(
                    since_hours=options["since_hours"],
                    wipe=True,
                    rollup_code=None,
                )
            else:
                written = run_feed_rollups(since_hours=options["since_hours"])
                self.stdout.write(f"Rebuilt {written} rollup events")
