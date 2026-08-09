"""
Copy market health snapshot rows from production_readonly into local default.

Ensures referenced EveLocation rows exist locally. Writes only to default.
Preserves production captured_at timestamps (auto_now_add would otherwise
overwrite).

Usage (from backend/, with DB_READONLY_* / production_readonly configured):

    pipenv run python manage.py import_market_health_snapshots_from_production
    pipenv run python manage.py import_market_health_snapshots_from_production --clear
    pipenv run python manage.py import_market_health_snapshots_from_production --dry-run

Options:
    --clear     Delete all local health snapshot rows before import.
    --dry-run   Validate and report counts without writing to default.
    --source    Database alias to read from (default: production_readonly).
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction

from eveonline.models import EveLocation
from market.models.health_snapshot import EveMarketHealthSnapshot

LOCATION_SKIP_COPY = frozenset(
    {"location_id", "deleted", "deleted_by_cascade"}
)
BATCH = 500


class Command(BaseCommand):
    help = (
        "Import market health snapshot history from production_readonly "
        "into the local default database."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="production_readonly",
            help="Django DB alias to read from (default: production_readonly).",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Remove all local health snapshots before import.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not write; only validate and print planned counts.",
        )

    def handle(self, *args, **options):
        source = options["source"]
        local = "default"
        self._validate_aliases(source, local)

        model = EveMarketHealthSnapshot
        loc_ids = set(
            model.objects.using(source)
            .values_list("location_id", flat=True)
            .distinct()
        )
        self._report_model(model, source, local)

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        with transaction.atomic(using=local):
            if options["clear"]:
                deleted, _ = model.objects.using(local).all().delete()
                self.stdout.write(
                    self.style.WARNING(
                        f"Cleared local {model.__name__} ({deleted})."
                    )
                )

            for lid in sorted(loc_ids):
                self._ensure_location(lid, source, local)

            imported = self._copy_snapshots(model, source, local)
            local_after = model.objects.using(local).count()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Imported {imported} {model.__name__} rows. "
                    f"Local count={local_after}."
                )
            )

    def _report_model(self, model, source: str, local: str):
        source_count = model.objects.using(source).count()
        local_before = model.objects.using(local).count()
        self.stdout.write(
            f"{model.__name__}: source={source_count}, local={local_before}."
        )

    def _validate_aliases(self, source, local):
        if source not in settings.DATABASES:
            raise CommandError(
                f'Database alias "{source}" is not configured. '
                "Set production_readonly (see app settings / DB_READONLY_*)."
            )
        if source == local:
            raise CommandError("Source and destination must differ.")

    def _ensure_location(self, location_id, source, local):
        existing = (
            EveLocation.all_objects.using(local).filter(pk=location_id).first()
        )
        if existing and not existing.deleted:
            return

        loc = EveLocation.objects.using(source).filter(pk=location_id).first()
        if not loc:
            raise CommandError(
                f"EveLocation {location_id} referenced by snapshots but "
                f"missing on source={source}."
            )

        fields = {
            field.name: getattr(loc, field.name)
            for field in EveLocation._meta.concrete_fields  # pylint: disable=protected-access
            if field.name not in LOCATION_SKIP_COPY
        }
        if existing:
            for key, value in fields.items():
                setattr(existing, key, value)
            existing.deleted = None
            existing.deleted_by_cascade = False
            try:
                existing.save(using=local)
            except ValidationError:
                existing.price_baseline = False
                existing.staging_active = False
                existing.save(using=local)
            self.stdout.write(
                f"  Restored EveLocation {location_id} ({loc.short_name})."
            )
            return

        obj = EveLocation(location_id=location_id, **fields)
        try:
            obj.save(using=local)
        except ValidationError:
            obj.price_baseline = False
            obj.staging_active = False
            obj.save(using=local)
        self.stdout.write(
            f"  Copied EveLocation {location_id} ({loc.short_name})."
        )

    def _copy_snapshots(self, model, source: str, local: str):
        table = model._meta.db_table
        write_cols = sorted(
            {field.column for field in model._meta.concrete_fields}
        )
        write_col_sql = ", ".join(f"`{c}`" for c in write_cols)
        placeholders = ", ".join(["%s"] * len(write_cols))
        insert_sql = (
            f"INSERT INTO `{table}` ({write_col_sql}) VALUES ({placeholders})"
        )

        last_pk = 0
        imported = 0
        while True:
            rows = list(
                model.objects.using(source)
                .filter(pk__gt=last_pk)
                .order_by("pk")
                .values(*write_cols)[:BATCH]
            )
            if not rows:
                break
            last_pk = rows[-1]["id"]

            batch_values = []
            for row in rows:
                batch_values.append([row[col] for col in write_cols])

            with connections[local].cursor() as cursor:
                cursor.executemany(insert_sql, batch_values)

            imported += len(rows)
            self.stdout.write(f"  {model.__name__} {imported}…")

        return imported
