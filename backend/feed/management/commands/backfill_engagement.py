from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from feed.helpers.zkill_history import backfill_engagement
from feed.management.commands.rebuild_feed_clusters import (
    Command as RebuildClustersCommand,
)
from feed.management.commands.rebuild_feed_rollups import (
    Command as RebuildRollupsCommand,
)


class Command(BaseCommand):
    help = (
        "Backfill engagement kills around an anchor killmail via zKill history"
    )

    def add_arguments(self, parser):
        parser.add_argument("--anchor-killmail", type=int, required=True)
        parser.add_argument("--window-minutes", type=int, default=30)
        parser.add_argument("--rebuild", action="store_true")

    def handle(self, *args, **options):
        anchor_id = options["anchor_killmail"]
        try:
            stats = backfill_engagement(
                anchor_id,
                window_minutes=options["window_minutes"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(str(stats))
        if options["rebuild"]:
            RebuildClustersCommand().handle(since_hours=48)
            RebuildRollupsCommand().handle(
                rollup_code="fleet_active",
                since_hours=48,
                wipe=False,
            )
