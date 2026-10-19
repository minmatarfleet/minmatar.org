from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from fleets.helpers.fights.backfill import (
    MAX_PAGES,
    SLEEP_SECONDS,
    backfill,
    backfill_fleets,
)


class Command(BaseCommand):
    help = (
        "Build the kills cards and settled fight timelines of tracked "
        "fleets from the last N days, filling missed killmails from zKill"
    )

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument(
            "--fleet",
            dest="fleet_ids",
            type=int,
            action="append",
            help="Only this fleet id (repeatable)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Rebuild fleets whose timeline is already settled",
        )
        parser.add_argument(
            "--no-zkill",
            dest="zkill",
            action="store_false",
            help="Use only the killmails the feed already has",
        )
        parser.add_argument("--max-pages", type=int, default=MAX_PAGES)
        parser.add_argument("--sleep", type=float, default=SLEEP_SECONDS)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List the fleets that would be backfilled",
        )

    def handle(self, *args, **options):
        since = timezone.now() - timedelta(days=options["days"])
        fleets = backfill_fleets(
            since, fleet_ids=options["fleet_ids"], force=options["force"]
        )
        self.stdout.write(f"{len(fleets)} fleets to backfill")
        for fleet in fleets:
            self.stdout.write(
                f"  {fleet.id} {fleet.type} {fleet.start_time:%Y-%m-%d %H:%M}"
            )
        if options["dry_run"] or not fleets:
            return

        stats = backfill(
            fleets,
            zkill=options["zkill"],
            max_pages=options["max_pages"],
            sleep_seconds=options["sleep"],
        )
        if options["zkill"]:
            self.stdout.write(f"zKill: {stats['zkill']}")
        for fleet_id, row in stats["fleets"].items():
            self.stdout.write(f"  {fleet_id}: {row}")
        failed = sum(1 for row in stats["fleets"].values() if "error" in row)
        self.stdout.write(
            self.style.SUCCESS(
                f"Backfilled {len(fleets) - failed} fleets, {failed} failed"
            )
        )
