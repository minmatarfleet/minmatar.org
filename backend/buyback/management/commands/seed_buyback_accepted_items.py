from django.core.management.base import BaseCommand

from buyback.helpers.accepted_items import (
    DEFAULT_PI_LOOKBACK_DAYS,
    seed_accepted_items,
)


class Command(BaseCommand):
    help = (
        "Seed buyback accepted items (compressed buyback ores + PI used in "
        "recent industry orders)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--deactivate-missing",
            action="store_true",
            help=(
                "Also deactivate active ore rows not in the default ore seed "
                "set. PI outside the lookback window is always deactivated."
            ),
        )
        parser.add_argument(
            "--pi-lookback-days",
            type=int,
            default=DEFAULT_PI_LOOKBACK_DAYS,
            help=(
                "Only accept PI appearing in industry-order BOMs created "
                f"within this many days (default {DEFAULT_PI_LOOKBACK_DAYS})."
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
