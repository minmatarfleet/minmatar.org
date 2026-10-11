"""
Copy all EveLocation rows from production_readonly into the local default database.

Usage (from backend/, with production_readonly configured):

    pipenv run python manage.py import_evelocations_from_production
    pipenv run python manage.py import_evelocations_from_production --dry-run
    pipenv run python manage.py import_evelocations_from_production --enable-jita-fleets
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction

from eveonline.helpers.production_import import validate_source_alias
from eveonline.models import EveLocation

LOCATION_SKIP_COPY = frozenset(
    {"location_id", "deleted", "deleted_by_cascade"}
)
JITA_LOCATION_ID = 60003760


def _source_location_columns(source: str) -> set[str]:
    with connections[source].cursor() as cursor:
        cursor.execute("SHOW COLUMNS FROM eveonline_evelocation")
        return {row[0] for row in cursor.fetchall()}


class Command(BaseCommand):
    help = (
        "Import all EveLocation rows from production_readonly "
        "into the local default database."
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
            help="Do not write; only validate and print planned work.",
        )
        parser.add_argument(
            "--enable-jita-fleets",
            action="store_true",
            help="After import, set Jita (60003760) fleets_active=True.",
        )

    def handle(self, *args, **options):
        source = options["source"]
        local = "default"
        validate_source_alias(source, local)
        source_columns = _source_location_columns(source)
        copy_fields = [
            field.name
            for field in EveLocation._meta.concrete_fields  # pylint: disable=protected-access
            if field.name not in LOCATION_SKIP_COPY
            and field.name in source_columns
        ]
        if "location_id" not in source_columns:
            raise CommandError(
                "Source EveLocation table is missing location_id."
            )

        prod_rows = (
            EveLocation.all_objects.using(source)
            .values("location_id", *copy_fields)
            .order_by("location_id")
        )
        prod_locations = list(prod_rows)
        self.stdout.write(
            f"Source={source}: {len(prod_locations)} EveLocation rows "
            f"({len(copy_fields)} copyable fields)."
        )

        if options["dry_run"]:
            local_ids = set(
                EveLocation.all_objects.using(local).values_list(
                    "location_id", flat=True
                )
            )
            prod_ids = {row["location_id"] for row in prod_locations}
            self.stdout.write(
                f"Local has {len(local_ids)} rows; "
                f"would create {len(prod_ids - local_ids)}, "
                f"update {len(prod_ids & local_ids)}."
            )
            if options["enable_jita_fleets"]:
                self.stdout.write("Would enable fleets_active on Jita.")
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        created = 0
        updated = 0
        with transaction.atomic(using=local):
            EveLocation.all_objects.using(local).update(
                staging_active=False,
                price_baseline=False,
            )
            for row in prod_locations:
                was_created = self._upsert_location(row, local, copy_fields)
                if was_created:
                    created += 1
                else:
                    updated += 1

            if options["enable_jita_fleets"]:
                jita = self._enable_jita_fleets(local)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Enabled fleets_active on Jita ({jita.location_name})."
                    )
                )

        local_count = EveLocation.all_objects.using(local).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. created={created} updated={updated} "
                f"local_total={local_count}"
            )
        )

    def _upsert_location(
        self, row: dict, local: str, copy_fields: list[str]
    ) -> bool:
        location_id = row["location_id"]
        fields = {name: row[name] for name in copy_fields}
        existing = (
            EveLocation.all_objects.using(local).filter(pk=location_id).first()
        )
        if existing:
            for key, value in fields.items():
                setattr(existing, key, value)
            existing.deleted = None
            existing.deleted_by_cascade = False
            try:
                existing.save(using=local)
            except ValidationError:
                existing.price_baseline = False
                existing.save(using=local)
            return False

        obj = EveLocation(location_id=location_id, **fields)
        try:
            obj.save(using=local)
        except ValidationError:
            obj.price_baseline = False
            obj.save(using=local)
        return True

    def _enable_jita_fleets(self, local: str) -> EveLocation:
        jita = (
            EveLocation.all_objects.using(local)
            .filter(location_id=JITA_LOCATION_ID)
            .first()
        )
        if jita is None:
            jita = (
                EveLocation.all_objects.using(local)
                .filter(short_name="Jita")
                .first()
            )
        if jita is None:
            raise ValueError("Jita EveLocation not found after import.")

        if not jita.fleets_active:
            jita.fleets_active = True
            jita.save(
                using=local, update_fields=["fleets_active", "updated_at"]
            )
        return jita
