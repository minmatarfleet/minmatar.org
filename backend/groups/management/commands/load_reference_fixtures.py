"""
Load committed reference fixtures into the default database.

Usage:

    pipenv run python manage.py load_reference_fixtures
    pipenv run python manage.py load_reference_fixtures --clear
"""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from fixtures.export import FIXTURE_FILES, missing_eve_type_ids
from fixtures.load import clear_reference_data, load_fixture_dir


class Command(BaseCommand):
    help = "Load reference fixture JSON files into the default database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fixture-dir",
            default="fixtures/data",
            help="Directory containing fixture JSON files (default: fixtures/data).",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing reference rows before loading.",
        )
        parser.add_argument(
            "--skip-eve-type-check",
            action="store_true",
            help="Do not abort when EveType rows are missing locally.",
        )

    def handle(self, *args, **options):
        fixture_dir = Path(options["fixture_dir"])
        if not fixture_dir.is_absolute():
            fixture_dir = Path(settings.BASE_DIR) / fixture_dir

        if not fixture_dir.is_dir():
            raise CommandError(f"Fixture directory not found: {fixture_dir}")

        missing_files = [
            name for name in FIXTURE_FILES if not (fixture_dir / name).exists()
        ]
        if missing_files:
            raise CommandError(
                f"Missing fixture files in {fixture_dir}: {', '.join(missing_files)}"
            )

        if not options["skip_eve_type_check"]:
            self._check_eve_types(fixture_dir)

        with transaction.atomic():
            if options["clear"]:
                deleted = clear_reference_data()
                self.stdout.write(
                    self.style.WARNING(
                        "Cleared reference tables: "
                        + ", ".join(
                            f"{k}={v}" for k, v in deleted.items() if v
                        )
                    )
                )
            load_fixture_dir(fixture_dir, stdout=self.stdout)

        self.stdout.write(self.style.SUCCESS("Reference fixtures loaded."))

    def _check_eve_types(self, fixture_dir: Path):
        """Parse tribe/market fixtures for EveType FKs and validate."""
        type_ids: set[int] = set()
        for name in (
            "06_tribes.json",
            "08_market_expectations.json",
        ):
            path = fixture_dir / name
            if not path.exists():
                continue
            rows = json.loads(path.read_text(encoding="utf-8"))
            for row in rows:
                model = row.get("model", "")
                fields = row.get("fields", {})
                if model == "tribes.tribegrouprequirementskill":
                    if fields.get("eve_type"):
                        type_ids.add(fields["eve_type"])
                elif model == "tribes.tribegrouprequirementassettype":
                    if fields.get("eve_type"):
                        type_ids.add(fields["eve_type"])
                elif model == "market.evemarketitemexpectation":
                    if fields.get("item"):
                        type_ids.add(fields["item"])

        missing = missing_eve_type_ids(type_ids)
        if missing:
            raise CommandError(
                "Local default DB is missing EveType rows for EVE type IDs: "
                f"{missing[:20]}{'…' if len(missing) > 20 else ''}. "
                "Load eveuniverse data locally first, or pass --skip-eve-type-check."
            )
