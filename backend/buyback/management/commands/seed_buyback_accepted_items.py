from django.core.management.base import BaseCommand

from buyback.helpers.accepted_items import (
    DEFAULT_PI_LOOKBACK_DAYS,
    seed_accepted_items,
)


class Command(BaseCommand):
    help = (
        "Seed buyback accepted items (compressed buyback ores, all published "
        "P1/P2, and P3/P4 used in recent industry orders)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--deactivate-missing",
            action="store_true",
            help=(
                "Also deactivate active ore rows not in the default ore seed "
                "set. P3/P4 outside the lookback window are always "
                "deactivated; P1/P2 stay as a full catalog."
            ),
        )
        parser.add_argument(
            "--pi-lookback-days",
            type=int,
            default=DEFAULT_PI_LOOKBACK_DAYS,
            help=(
                "Only accept P3/P4 appearing in industry-order BOMs created "
                f"within this many days (default {DEFAULT_PI_LOOKBACK_DAYS}). "
                "All published P1/P2 are always seeded."
            ),
        )

    def handle(self, *args, **options):
        result = seed_accepted_items(
            deactivate_missing=options["deactivate_missing"],
            pi_lookback_days=options["pi_lookback_days"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Buyback accepted items: "
                f"seeded={result['seeded']} pi={result['pi_seeded']} "
                f"created={result['created']} updated={result['updated']} "
                f"deactivated={result['deactivated']} "
                f"(pi={result['deactivated_pi']})"
            )
        )
