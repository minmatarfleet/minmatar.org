"""Fix imported Reddit posts that lost gallery images or a Reddit video.

Dry run by default: lists what would change. Pass --apply to write.
"""

from django.core.management.base import BaseCommand

from creators.reddit_media_backfill import backfill_reddit_media


class Command(BaseCommand):
    help = "Rebuild imported Reddit posts with all gallery images and Reddit video players."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the changes (default: dry run).",
        )

    def handle(self, *args, **options):
        fixes = backfill_reddit_media(apply=options["apply"])
        for fix in fixes:
            self.stdout.write(f"#{fix.post_id} {fix.title[:60]}: {fix.reason}")
        verb = "Updated" if options["apply"] else "Would update"
        self.stdout.write(f"{verb} {len(fixes)} post(s).")
