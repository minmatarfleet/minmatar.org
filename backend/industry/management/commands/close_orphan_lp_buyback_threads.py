"""Archive leftover LP buyback Discord forum threads."""

from django.core.management.base import BaseCommand

from industry.helpers.lp_buyback_discord import (
    ORPHAN_LP_BUYBACK_THREAD_IDS,
    close_lp_buyback_thread_id,
)


class Command(BaseCommand):
    help = "Archive leftover LP buyback Discord threads."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print thread ids without calling Discord.",
        )

    def handle(self, *args, **options):
        if options["dry_run"]:
            for thread_id in ORPHAN_LP_BUYBACK_THREAD_IDS:
                self.stdout.write(str(thread_id))
            return

        closed = 0
        for thread_id in ORPHAN_LP_BUYBACK_THREAD_IDS:
            if close_lp_buyback_thread_id(thread_id):
                closed += 1
        self.stdout.write(self.style.SUCCESS(f"closed={closed}"))
