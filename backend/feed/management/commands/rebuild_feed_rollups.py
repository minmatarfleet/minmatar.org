from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from feed.models import FeedEvent
from feed.rollups.registry import ROLLUP_PROCESSORS, build_context, run_rollup
from feed.rollups.writer import write_rollup_results


class Command(BaseCommand):
    help = "Rebuild derived FeedEvent rows from facts/clusters"

    def add_arguments(self, parser):
        parser.add_argument("--rollup", dest="rollup_code", default=None)
        parser.add_argument(
            "--since", dest="since_hours", type=int, default=48
        )
        parser.add_argument(
            "--wipe",
            action="store_true",
            help="Delete existing derived events first",
        )

    def handle(self, *args, **options):
        rollup_code = options["rollup_code"]
        since_hours = options["since_hours"]
        now = timezone.now()
        since = now - timedelta(hours=since_hours)
        ctx = build_context(since, now)

        codes = (
            [rollup_code] if rollup_code else list(ROLLUP_PROCESSORS.keys())
        )
        if options["wipe"]:
            deleted, _ = FeedEvent.objects.filter(
                rollup_code__in=codes
            ).delete()
            self.stdout.write(f"Deleted {deleted} existing events")

        total = 0
        for code in codes:
            results = run_rollup(code, ctx)
            written = write_rollup_results(results)
            total += written
            self.stdout.write(f"{code}: wrote {written} events")

        self.stdout.write(
            self.style.SUCCESS(f"Rebuild complete: {total} events")
        )
