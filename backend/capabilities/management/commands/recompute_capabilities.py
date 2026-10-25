"""Recompute fitting requirements, readiness and capabilities now."""

from django.core.management.base import BaseCommand

from capabilities import services
from capabilities.tasks import recompute_everything


class Command(BaseCommand):
    help = "Recompute every doctrine fitting, then readiness and capabilities."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recompute fittings even when their inputs did not change.",
        )
        parser.add_argument(
            "--accounts",
            action="store_true",
            help="Also rebuild account links from fleet seats.",
        )

    def handle(self, *args, **options):
        result = recompute_everything(force=options["force"])
        if options["accounts"]:
            result["account_links"] = services.refresh_account_links()
        self.stdout.write(str(result))
