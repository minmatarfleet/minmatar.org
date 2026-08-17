"""
Copy AllianceHealthSnapshot rows from production_readonly into local default.

Reads production via the read-only alias; writes only to default. Snapshots
are JSON rollups with no foreign keys, so this is sufficient to iterate on
the health dashboard without recomputing from roster/fleet/kill data.

Usage (from backend/, with DB_READONLY_* / production_readonly configured):

    pipenv run python manage.py import_alliance_health_from_production
    pipenv run python manage.py import_alliance_health_from_production --clear
    pipenv run python manage.py import_alliance_health_from_production --dry-run

Options:
    --clear     Delete all local snapshots before import.
    --dry-run   Validate and report counts without writing to default.
    --source    Database alias to read from (default: production_readonly).
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from alliance.models import AllianceHealthSnapshot
from eveonline.helpers.production_import import validate_source_alias

SNAPSHOT_FIELDS = ("computed_at", "payload")


class Command(BaseCommand):
    help = (
        "Import alliance health snapshots from production_readonly "
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
            help="Remove all local AllianceHealthSnapshot rows before import.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not write; only validate and print planned counts.",
        )

    def handle(self, *args, **options):
        source = options["source"]
        local = "default"
        validate_source_alias(source, local)

        prod_snaps = list(
            AllianceHealthSnapshot.objects.using(source).order_by("pk")
        )
        local_before = AllianceHealthSnapshot.objects.using(local).count()
        self.stdout.write(
            f"AllianceHealthSnapshot: source={len(prod_snaps)}, "
            f"local={local_before}."
        )
        if prod_snaps:
            latest = max(prod_snaps, key=lambda row: row.computed_at)
            self.stdout.write(
                f"  Latest source id={latest.pk} "
                f"computed_at={latest.computed_at.isoformat()}."
            )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        with transaction.atomic(using=local):
            if options["clear"]:
                deleted, _ = (
                    AllianceHealthSnapshot.objects.using(local).all().delete()
                )
                self.stdout.write(
                    self.style.WARNING(
                        f"Cleared local AllianceHealthSnapshot ({deleted})."
                    )
                )

            created = 0
            updated = 0
            for prod in prod_snaps:
                defaults = {
                    field: getattr(prod, field) for field in SNAPSHOT_FIELDS
                }
                _, was_created = AllianceHealthSnapshot.objects.using(
                    local
                ).update_or_create(pk=prod.pk, defaults=defaults)
                if was_created:
                    created += 1
                else:
                    updated += 1

        local_after = AllianceHealthSnapshot.objects.using(local).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. created={created} updated={updated} "
                f"local_total={local_after}."
            )
        )
