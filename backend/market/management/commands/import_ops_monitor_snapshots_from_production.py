"""
Copy EveMarketOpsMonitorSnapshot rows (ops monitor health-over-time history)
from production_readonly into the local default database.

Ensures referenced EveLocation rows exist locally. Writes only to default.
Preserves production captured_at timestamps (auto_now_add would otherwise
overwrite). Handles schema drift for contracts_viability_pct /
contract_viable_fulfilled when either DB lacks those columns yet.

Usage (from backend/, with DB_READONLY_* / production_readonly configured):

    pipenv run python manage.py import_ops_monitor_snapshots_from_production
    pipenv run python manage.py import_ops_monitor_snapshots_from_production --clear
    pipenv run python manage.py import_ops_monitor_snapshots_from_production --dry-run

Options:
    --clear     Delete all local snapshot rows before import (clean prod mirror).
    --dry-run   Validate and report counts without writing to default.
    --source    Database alias to read from (default: production_readonly).
"""

import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connections, transaction

from eveonline.models import EveLocation
from market.models.ops_snapshot import EveMarketOpsMonitorSnapshot

LOCATION_SKIP_COPY = frozenset(
    {"location_id", "deleted", "deleted_by_cascade"}
)
BATCH = 500

# Newer than migration 0031; may be absent on source and/or local until 0036+.
OPTIONAL_COLUMNS = frozenset(
    {
        "contracts_viability_pct",
        "contract_viable_fulfilled",
    }
)

OPTIONAL_DEFAULTS = {
    "contracts_viability_pct": None,
    "contract_viable_fulfilled": 0,
}

# JSONField values must be serialized for raw INSERT (MySQL).
JSON_COLUMNS = frozenset({"understocked_contracts", "sell_gaps"})


class Command(BaseCommand):
    help = (
        "Import EveMarketOpsMonitorSnapshot history from production_readonly "
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
            help="Remove all local ops monitor snapshots before import.",
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

        table = EveMarketOpsMonitorSnapshot._meta.db_table
        source_cols = self._table_columns(source, table)
        local_cols = self._table_columns(local, table)
        model_cols = self._model_db_columns()

        read_cols = sorted(model_cols & source_cols)
        write_cols = sorted(model_cols & local_cols)
        if "id" not in read_cols or "location_id" not in read_cols:
            raise CommandError(
                f"Source table {table} missing required columns "
                f"(need id, location_id); have {sorted(source_cols)}."
            )
        if "id" not in write_cols or "location_id" not in write_cols:
            raise CommandError(
                f"Local table {table} missing required columns "
                f"(need id, location_id); have {sorted(local_cols)}."
            )

        skipped_optional = sorted(
            OPTIONAL_COLUMNS - (source_cols & local_cols)
        )
        source_count = EveMarketOpsMonitorSnapshot.objects.using(
            source
        ).count()
        local_before = EveMarketOpsMonitorSnapshot.objects.using(local).count()
        date_range = self._date_range(source)

        loc_ids = set(
            EveMarketOpsMonitorSnapshot.objects.using(source)
            .values_list("location_id", flat=True)
            .distinct()
        )

        self.stdout.write(
            f"Source={source}: {source_count} snapshots "
            f"(captured_at {date_range[0]} … {date_range[1]})."
        )
        self.stdout.write(
            f"Local {local} before: {local_before}. "
            f"Locations referenced: {len(loc_ids)}."
        )
        self.stdout.write(
            f"Copy columns ({len(write_cols)}): {', '.join(write_cols)}"
        )
        if skipped_optional:
            self.stdout.write(
                self.style.WARNING(
                    "Optional columns absent on source and/or local "
                    f"(will use defaults / omit): {', '.join(skipped_optional)}"
                )
            )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        with transaction.atomic(using=local):
            if options["clear"]:
                deleted, _ = (
                    EveMarketOpsMonitorSnapshot.objects.using(local)
                    .all()
                    .delete()
                )
                self.stdout.write(
                    self.style.WARNING(f"Cleared local snapshots ({deleted}).")
                )

            for lid in sorted(loc_ids):
                self._ensure_location(lid, source, local)

            imported = self._copy_snapshots(
                source=source,
                local=local,
                read_cols=read_cols,
                write_cols=write_cols,
            )

        local_after = EveMarketOpsMonitorSnapshot.objects.using(local).count()
        local_range = self._date_range(local)
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {imported} snapshots into {local}. "
                f"Local count={local_after} "
                f"(captured_at {local_range[0]} … {local_range[1]})."
            )
        )

    def _validate_aliases(self, source, local):
        if source not in settings.DATABASES:
            raise CommandError(
                f'Database alias "{source}" is not configured. '
                "Set production_readonly (see app settings / DB_READONLY_*)."
            )
        if source == local:
            raise CommandError("Source and destination must differ.")

    def _model_db_columns(self):
        cols = set()
        for field in EveMarketOpsMonitorSnapshot._meta.concrete_fields:
            cols.add(field.column)
        return cols

    def _table_columns(self, alias, table):
        connection = connections[alias]
        with connection.cursor() as cursor:
            description = connection.introspection.get_table_description(
                cursor, table
            )
        return {col.name for col in description}

    def _date_range(self, alias):
        qs = EveMarketOpsMonitorSnapshot.objects.using(alias)
        earliest = (
            qs.order_by("captured_at")
            .values_list("captured_at", flat=True)
            .first()
        )
        latest = (
            qs.order_by("-captured_at")
            .values_list("captured_at", flat=True)
            .first()
        )
        return earliest, latest

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

    def _copy_snapshots(self, *, source, local, read_cols, write_cols):
        """
        Keyset-paginate source rows and INSERT into local with only columns
        that exist on each side. Uses raw SQL so model fields absent from the
        physical table (e.g. pre-0036 viability columns) do not break INSERT,
        and so captured_at is preserved despite auto_now_add.
        """
        table = EveMarketOpsMonitorSnapshot._meta.db_table
        last_pk = 0
        imported = 0
        write_col_sql = ", ".join(f"`{c}`" for c in write_cols)
        placeholders = ", ".join(["%s"] * len(write_cols))
        insert_sql = (
            f"INSERT INTO `{table}` ({write_col_sql}) VALUES ({placeholders})"
        )

        while True:
            rows = list(
                EveMarketOpsMonitorSnapshot.objects.using(source)
                .filter(pk__gt=last_pk)
                .order_by("pk")
                .values(*read_cols)[:BATCH]
            )
            if not rows:
                break
            last_pk = rows[-1]["id"]

            batch_values = []
            for row in rows:
                values = []
                for col in write_cols:
                    if col in row:
                        value = row[col]
                    else:
                        value = OPTIONAL_DEFAULTS.get(col)
                    if col in JSON_COLUMNS:
                        value = json.dumps(
                            value if value is not None else [],
                            cls=DjangoJSONEncoder,
                        )
                    values.append(value)
                batch_values.append(values)

            with connections[local].cursor() as cursor:
                cursor.executemany(insert_sql, batch_values)

            imported += len(rows)
            self.stdout.write(f"  snapshots {imported}…")

        return imported
