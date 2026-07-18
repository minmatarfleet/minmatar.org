"""
Export non-sensitive reference data from production_readonly into Django JSON fixtures.

Usage (from backend/, with production_readonly configured):

    pipenv run python manage.py export_reference_fixtures
    pipenv run python manage.py export_reference_fixtures --dry-run
    pipenv run python manage.py export_reference_fixtures --include-history
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from fixtures.export import (
    collect_eve_type_ids,
    collect_reference_data,
    bundle_counts,
    missing_eve_type_ids,
    write_fixture_files,
)


class Command(BaseCommand):
    help = (
        "Export non-sensitive reference data from production_readonly "
        "into Django JSON fixture files."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="production_readonly",
            help="Django DB alias to read from (default: production_readonly).",
        )
        parser.add_argument(
            "--output-dir",
            default="fixtures/data",
            help="Directory for JSON fixture files (default: fixtures/data).",
        )
        parser.add_argument(
            "--include-history",
            action="store_true",
            help="Include EveFittingHistory and EveDoctrineHistory rows.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print row counts without writing files.",
        )
        parser.add_argument(
            "--check-eve-types",
            action="store_true",
            help="Warn if default DB is missing referenced EveType rows.",
        )

    def handle(self, *args, **options):
        source = options["source"]
        if source not in settings.DATABASES:
            raise CommandError(
                f'Database alias "{source}" is not configured. '
                "Set production_readonly (see app settings / DB_READONLY_*)."
            )

        self.stdout.write(f"Collecting reference data from {source}…")
        bundle = collect_reference_data(
            source, include_history=options["include_history"]
        )

        counts = bundle_counts(bundle)
        for label, count in counts.items():
            if count or not label.endswith("History"):
                self.stdout.write(f"  {label}: {count}")

        if options["check_eve_types"]:
            missing = missing_eve_type_ids(collect_eve_type_ids(bundle))
            if missing:
                self.stdout.write(
                    self.style.WARNING(
                        "Default DB missing EveType rows for IDs: "
                        f"{missing[:20]}{'…' if len(missing) > 20 else ''}. "
                        "Load eveuniverse data locally before loading fixtures."
                    )
                )

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING("Dry run — no files written.")
            )
            return

        output_dir = Path(options["output_dir"])
        if not output_dir.is_absolute():
            output_dir = Path(settings.BASE_DIR) / output_dir

        written = write_fixture_files(bundle, output_dir)
        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {len(written)} fixture files to {output_dir}:"
            )
        )
        for filename, count in written.items():
            self.stdout.write(f"  {filename}: {count} rows")

        readme = output_dir / "README.md"
        readme.write_text(_readme_content(), encoding="utf-8")
        self.stdout.write("  README.md")


def _readme_content() -> str:
    return """# Reference fixtures

Non-sensitive production configuration exported for local development.

**Fittings are not included.** Doctrine fits must not be wiped by fixture load;
sync fittings separately when needed.

## Prerequisites

1. Run migrations: `pipenv run python manage.py migrate`
2. Load EVE universe types locally: `pipenv run python manage.py eveuniverse_load_types`
3. Ensure required EveFitting rows exist before loading doctrines / market expectations

## Load

```bash
pipenv run python manage.py load_reference_fixtures
```

Use `--clear` to remove existing reference rows before loading. This does
**not** delete fittings or refits.

## Regenerate (maintainers with production_readonly access)

```bash
pipenv run python manage.py export_reference_fixtures
```

Files load in numeric order (`01_` … `10_`). Do not reorder without updating `fixtures/export.py` and `load_reference_fixtures`.
"""
