from django.core.management.base import BaseCommand

from buyback.helpers.refresh import refresh_buyback_ledger


class Command(BaseCommand):
    help = (
        "Refresh buyback stock ledger: contract in/out items, market sell "
        "fills, hangar snapshot/Unknown residuals, and accepted-item metrics."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-contracts",
            action="store_true",
            help="Skip ESI contract item sync.",
        )
        parser.add_argument(
            "--skip-sell-orders",
            action="store_true",
            help="Skip corp wallet sell-transaction sync.",
        )
        parser.add_argument(
            "--skip-hangar",
            action="store_true",
            help="Skip hangar snapshot / Unknown residuals.",
        )
        parser.add_argument(
            "--skip-metrics",
            action="store_true",
            help="Skip accepted-item demand/stockpile metrics.",
        )
        parser.add_argument(
            "--skip-seed",
            action="store_true",
            help="When refreshing metrics, do not re-seed the allowlist.",
        )

    def handle(self, *args, **options):
        result = refresh_buyback_ledger(
            sync_contracts=not options["skip_contracts"],
            sync_sell_orders=not options["skip_sell_orders"],
            snapshot_hangar=not options["skip_hangar"],
            refresh_metrics=not options["skip_metrics"],
            seed_allowlist=not options["skip_seed"],
        )
        self.stdout.write(
            self.style.SUCCESS(f"Buyback ledger refresh: {result}")
        )
