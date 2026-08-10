"""
Record current contract and sell-order health snapshots from local DB.

    pipenv run python manage.py record_market_health_snapshots
    pipenv run python manage.py record_market_health_snapshots --contracts-only
    pipenv run python manage.py record_market_health_snapshots --sell-orders-only
    pipenv run python manage.py record_market_health_snapshots --location-id 1022167642188
"""

from django.core.management.base import BaseCommand

from market.helpers.health_snapshot import (
    record_contract_health_snapshots,
    record_sell_order_health_snapshots,
)


class Command(BaseCommand):
    help = (
        "Persist current market health snapshots for all (or one) "
        "market-active location(s)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--location-id",
            type=int,
            default=None,
            help="Optional ESI location_id to snapshot (default: all).",
        )
        parser.add_argument(
            "--contracts-only",
            action="store_true",
            help="Only record contract health snapshots.",
        )
        parser.add_argument(
            "--sell-orders-only",
            action="store_true",
            help="Only record sell-order health snapshots.",
        )

    def handle(self, *args, **options):
        location_id = options["location_id"]
        contracts_only = options["contracts_only"]
        sell_only = options["sell_orders_only"]
        if contracts_only and sell_only:
            self.stderr.write(
                "Choose at most one of --contracts-only / --sell-orders-only."
            )
            return

        if not sell_only:
            created = record_contract_health_snapshots(location_id=location_id)
            self.stdout.write(
                self.style.SUCCESS(f"Contract health snapshots: {created}")
            )
        if not contracts_only:
            created = record_sell_order_health_snapshots(
                location_id=location_id
            )
            self.stdout.write(
                self.style.SUCCESS(f"Sell-order health snapshots: {created}")
            )
