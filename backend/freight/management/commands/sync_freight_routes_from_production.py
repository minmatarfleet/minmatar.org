"""
Copy EveFreightRoute rows (and required EveLocation FKs) from production_readonly
into the local default database.

Reads production via the read-only alias; writes only to default. Upserts routes
by (origin_location_id, destination_location_id).

Usage (from backend/, with DB_READONLY_* / production_readonly configured):

    pipenv run python manage.py sync_freight_routes_from_production
    pipenv run python manage.py sync_freight_routes_from_production --clear
    pipenv run python manage.py sync_freight_routes_from_production --dry-run

Options:
    --clear     Delete all local EveFreightRoute rows before import.
    --dry-run   Validate and report planned work without writing to default.
    --source    Database alias to read from (default: production_readonly).
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from eveonline.models import EveLocation
from freight.models import EveFreightRoute

LOCATION_SKIP_COPY = frozenset(
    {"location_id", "deleted", "deleted_by_cascade"}
)
ROUTE_FIELDS = (
    "isk_per_m3",
    "collateral_modifier",
    "expiration_days",
    "days_to_complete",
    "active",
)


class Command(BaseCommand):
    help = (
        "Sync EveFreightRoute rows from production_readonly "
        "(or another alias) into the local default database."
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
            help="Remove all local EveFreightRoute rows before import.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not write; only validate and print planned work.",
        )

    def handle(self, *args, **options):
        source = options["source"]
        local = "default"
        self._validate_aliases(source, local)

        prod_routes = list(
            EveFreightRoute.objects.using(source)
            .select_related("origin_location", "destination_location")
            .order_by("pk")
        )
        loc_ids = self._gather_location_ids(prod_routes)
        missing_loc_ids = self._missing_local_location_ids(loc_ids, local)

        self.stdout.write(
            f"Source={source}: {len(prod_routes)} routes, "
            f"{len(loc_ids)} locations "
            f"({len(missing_loc_ids)} missing locally)."
        )
        for route in prod_routes:
            self._print_route_line(route, prefix="  prod ")

        if options["dry_run"]:
            if missing_loc_ids:
                self.stdout.write(
                    f"Would copy EveLocation ids: {sorted(missing_loc_ids)}"
                )
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        with transaction.atomic(using=local):
            if options["clear"]:
                deleted, _ = (
                    EveFreightRoute.objects.using(local).all().delete()
                )
                self.stdout.write(
                    self.style.WARNING(
                        f"Cleared local freight routes ({deleted} rows)."
                    )
                )

            for lid in sorted(loc_ids):
                self._ensure_location(lid, source, local)

            created = 0
            updated = 0
            for prod_route in prod_routes:
                was_created = self._upsert_route(prod_route, local)
                if was_created:
                    created += 1
                else:
                    updated += 1

        local_routes = list(
            EveFreightRoute.objects.using(local)
            .select_related("origin_location", "destination_location")
            .order_by("pk")
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Synced into {local}: {created} created, {updated} updated. "
                f"Local total={len(local_routes)} (prod={len(prod_routes)})."
            )
        )
        self.stdout.write("Local routes:")
        for route in local_routes:
            self._print_route_line(route, prefix="  ")

        self._verify_jita_amamake(local_routes)

    def _validate_aliases(self, source, local):
        if source not in settings.DATABASES:
            raise CommandError(
                f'Database alias "{source}" is not configured. '
                "Set production_readonly (see app settings / DB_READONLY_*)."
            )
        if source == local:
            raise CommandError("Source and destination must differ.")

    def _gather_location_ids(self, routes):
        loc_ids = set()
        for route in routes:
            if route.origin_location_id:
                loc_ids.add(route.origin_location_id)
            if route.destination_location_id:
                loc_ids.add(route.destination_location_id)
        return loc_ids

    def _missing_local_location_ids(self, loc_ids, local):
        present = set(
            EveLocation.objects.using(local)
            .filter(pk__in=loc_ids)
            .values_list("pk", flat=True)
        )
        return loc_ids - present

    def _ensure_location(self, location_id, source, local):
        existing = (
            EveLocation.all_objects.using(local).filter(pk=location_id).first()
        )
        if existing and not existing.deleted:
            return
        loc = EveLocation.objects.using(source).get(pk=location_id)
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
            obj.save(using=local)
        self.stdout.write(
            f"  Copied EveLocation {location_id} ({loc.short_name})."
        )

    def _upsert_route(self, prod_route, local):
        defaults = {
            field: getattr(prod_route, field) for field in ROUTE_FIELDS
        }
        existing = (
            EveFreightRoute.objects.using(local)
            .filter(
                origin_location_id=prod_route.origin_location_id,
                destination_location_id=prod_route.destination_location_id,
            )
            .first()
        )
        if existing:
            for key, value in defaults.items():
                setattr(existing, key, value)
            existing.save(using=local)
            return False
        EveFreightRoute.objects.using(local).create(
            origin_location_id=prod_route.origin_location_id,
            destination_location_id=prod_route.destination_location_id,
            **defaults,
        )
        return True

    def _print_route_line(self, route, *, prefix=""):
        origin = (
            route.origin_location.short_name if route.origin_location else "?"
        )
        dest = (
            route.destination_location.short_name
            if route.destination_location
            else "?"
        )
        collat_pct = route.collateral_modifier * 100
        self.stdout.write(
            f"{prefix}{origin} → {dest}: "
            f"{route.isk_per_m3} isk/m³, "
            f"{collat_pct:g}% collateral, "
            f"active={route.active}"
        )

    def _verify_jita_amamake(self, local_routes):
        matches = [
            r
            for r in local_routes
            if r.origin_location
            and r.destination_location
            and r.origin_location.short_name == "Jita"
            and r.destination_location.short_name == "Amamake"
            and r.active
        ]
        if not matches:
            self.stdout.write(
                self.style.ERROR(
                    "Verification failed: no active Jita → Amamake."
                )
            )
            return
        route = matches[0]
        self.stdout.write(
            self.style.SUCCESS(
                f"Verified Jita → Amamake: {route.isk_per_m3} isk/m³, "
                f"{route.collateral_modifier * 100:g}% collateral."
            )
        )
