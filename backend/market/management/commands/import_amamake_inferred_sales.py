"""
Load Amamake (or other) inferred-sale CSV into EveMarketInferredSale.

Default file: market/data/amamake_inferred_sales.csv

    pipenv run python manage.py import_amamake_inferred_sales --dry-run
    pipenv run python manage.py import_amamake_inferred_sales
    pipenv run python manage.py import_amamake_inferred_sales --replace-imported
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from market.helpers.import_inferred_sales_csv import (
    DEFAULT_CSV_PATH,
    import_inferred_sales_csv,
)


class Command(BaseCommand):
    help = (
        "Import structure inferred sales from a public CSV "
        "(default: market/data/amamake_inferred_sales.csv)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            type=str,
            default=str(DEFAULT_CSV_PATH),
            help="Path to inferred-sales CSV.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and report without writing.",
        )
        parser.add_argument(
            "--replace-imported",
            action="store_true",
            help=(
                "Delete existing reason=imported rows for locations in the "
                "CSV before inserting."
            ),
        )
        parser.add_argument(
            "--no-before-existing",
            action="store_true",
            help=(
                "Do not skip rows at/after the earliest existing sale for "
                "each location (risk of double-counting live sync)."
            ),
        )

    def handle(self, *args, **options):
        path = Path(options["csv"])
        try:
            result = import_inferred_sales_csv(
                path,
                dry_run=options["dry_run"],
                replace_imported=options["replace_imported"],
                before_existing=not options["no_before_existing"],
            )
        except FileNotFoundError as exc:
            raise CommandError(f"CSV not found: {exc}") from exc
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        mode = "dry-run" if options["dry_run"] else "imported"
        self.stdout.write(
            f"{mode}: read={result.read} created={result.created} "
            f"skipped_unknown_type={result.skipped_unknown_type} "
            f"skipped_overlap={result.skipped_overlap} "
            f"deleted_imported={result.deleted_imported} "
            f"locations={list(result.locations)}"
        )
