from __future__ import annotations

from django.core.management.base import BaseCommand

from feed.helpers.r2z2 import poll_r2z2_batch


class Command(BaseCommand):
    help = "Long-running R2Z2 poller (management command fallback for docker service)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Run one batch and exit (same as Celery task)",
        )

    def handle(self, *args, **options):
        if options["once"]:
            stats = poll_r2z2_batch()
            self.stdout.write(str(stats))
            return

        self.stdout.write("Starting R2Z2 poller (Ctrl+C to stop)...")
        while True:
            stats = poll_r2z2_batch()
            self.stdout.write(str(stats))
