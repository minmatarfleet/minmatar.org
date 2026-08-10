"""
Import industry products, orders, and buyback data from production_readonly
for local buyback / supply-chain verification.

Orchestrates:
  1. import_industry_products_from_production --clear
  2. import_industry_orders_from_production --clear
  3. import_buyback_from_production --clear --reseed [--history-days N]

Usage (from backend/, with DB_READONLY_* configured):

    pipenv run python manage.py import_buyback_supply_chain_from_production --dry-run
    pipenv run python manage.py import_buyback_supply_chain_from_production
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Import industry products, orders, and buyback settings/allowlist/"
        "history from production for local supply-chain buyback verification."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="production_readonly",
            help="Django DB alias to read from (default: production_readonly).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Pass --dry-run through to each import step.",
        )
        parser.add_argument(
            "--skip-history",
            action="store_true",
            help="Do not import EveMarketItemHistory (history-days=0).",
        )
        parser.add_argument(
            "--history-days",
            type=int,
            default=14,
            help="History lookback days for buyback types (default 14).",
        )

    def handle(self, *args, **options):
        source = options["source"]
        dry_run = options["dry_run"]
        history_days = (
            0 if options["skip_history"] else options["history_days"]
        )

        self.stdout.write(
            self.style.NOTICE(
                f"Importing buyback supply-chain mirror from {source} "
                f"(dry_run={dry_run}, history_days={history_days})…"
            )
        )

        common = {"source": source, "clear": True}
        if dry_run:
            common["dry_run"] = True

        self.stdout.write(self.style.NOTICE("1/3 Industry products…"))
        call_command(
            "import_industry_products_from_production",
            stdout=self.stdout,
            stderr=self.stderr,
            **common,
        )

        self.stdout.write(self.style.NOTICE("2/3 Industry orders…"))
        call_command(
            "import_industry_orders_from_production",
            stdout=self.stdout,
            stderr=self.stderr,
            **common,
        )

        self.stdout.write(self.style.NOTICE("3/3 Buyback settings + items…"))
        buyback_kwargs = {
            **common,
            "reseed": True,
            "history_days": history_days,
        }
        call_command(
            "import_buyback_from_production",
            stdout=self.stdout,
            stderr=self.stderr,
            **buyback_kwargs,
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING("Dry run complete — no changes made.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("Buyback supply-chain import complete.")
            )
