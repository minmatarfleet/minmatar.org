"""
Sync feed contested % data from production_readonly into the default database.

Copies active FeedMonitoredSystem rows. When the contested snapshot table exists
in production, copies FeedSystemContestedSnapshot rows as well. Otherwise use
--poll-esi to seed current readings from ESI after import.

Usage (from backend/, with production_readonly configured):

    pipenv run python manage.py migrate
    pipenv run python manage.py import_feed_contested_from_production --poll-esi

Options:
    --poll-esi          After import, poll ESI for current contested % snapshots.
    --clear-snapshots   Delete local contested snapshots before import.
    --dry-run           Validate and report counts without writing to default.
    --source            Database alias to read from (default: production_readonly).
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from django.db.utils import ProgrammingError

from feed.helpers.fw_contested import poll_monitored_contested_snapshots
from feed.helpers.monitored_systems import invalidate_monitored_systems_cache
from feed.models import FeedMonitoredSystem, FeedSystemContestedSnapshot


class Command(BaseCommand):
    help = (
        "Import feed monitored systems and contested snapshots from "
        "production_readonly into the local default database."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="production_readonly",
            help="Django DB alias to read from (default: production_readonly).",
        )
        parser.add_argument(
            "--clear-snapshots",
            action="store_true",
            help="Remove all local FeedSystemContestedSnapshot rows before import.",
        )
        parser.add_argument(
            "--poll-esi",
            action="store_true",
            help="Poll ESI /fw/systems/ for current contested % after import.",
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

        prod_systems = list(
            FeedMonitoredSystem.objects.using(source)
            .filter(is_active=True)
            .order_by("solar_system_id")
        )
        if not prod_systems:
            raise CommandError(
                f"No active FeedMonitoredSystem rows in {source}. "
                "Run seed_feed_monitored_systems in production first."
            )

        prod_snapshots = self._load_prod_snapshots(source)
        self.stdout.write(
            f"Source={source}: {len(prod_systems)} monitored systems, "
            f"{len(prod_snapshots)} contested snapshots."
        )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        with transaction.atomic(using=local):
            if options["clear_snapshots"]:
                deleted, _ = (
                    FeedSystemContestedSnapshot.objects.using(local)
                    .all()
                    .delete()
                )
                self.stdout.write(
                    self.style.WARNING(
                        f"Cleared {deleted} local contested snapshots."
                    )
                )

            created_systems = 0
            updated_systems = 0
            for row in prod_systems:
                _, created = FeedMonitoredSystem.objects.using(
                    local
                ).update_or_create(
                    solar_system_id=row.solar_system_id,
                    defaults={
                        "name": row.name,
                        "source": row.source,
                        "is_active": row.is_active,
                    },
                )
                if created:
                    created_systems += 1
                else:
                    updated_systems += 1

            snapshots_written = 0
            if prod_snapshots:
                FeedSystemContestedSnapshot.objects.using(local).bulk_create(
                    [
                        FeedSystemContestedSnapshot(
                            solar_system_id=snapshot.solar_system_id,
                            contested_percent=snapshot.contested_percent,
                            occupier_faction_id=snapshot.occupier_faction_id,
                            victor_faction_id=snapshot.victor_faction_id,
                            captured_at=snapshot.captured_at,
                        )
                        for snapshot in prod_snapshots
                    ],
                    ignore_conflicts=True,
                )
                snapshots_written = len(prod_snapshots)

        invalidate_monitored_systems_cache()

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported into {local}: {created_systems} systems created, "
                f"{updated_systems} updated, {snapshots_written} snapshots copied."
            )
        )

        if options["poll_esi"]:
            stats = poll_monitored_contested_snapshots()
            self.stdout.write(
                self.style.SUCCESS(f"ESI poll complete: {stats}")
            )
        elif not prod_snapshots:
            self.stdout.write(
                self.style.WARNING(
                    "No contested snapshots in production — run again with "
                    "--poll-esi to seed current readings from ESI."
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

    def _load_prod_snapshots(self, source):
        try:
            return list(
                FeedSystemContestedSnapshot.objects.using(source).order_by(
                    "captured_at", "solar_system_id"
                )
            )
        except ProgrammingError as exc:
            if "doesn't exist" in str(exc):
                self.stdout.write(
                    self.style.WARNING(
                        "Production contested snapshot table not found "
                        "(migration not deployed yet)."
                    )
                )
                return []
            raise
        except Exception as exc:
            with connections[source].cursor() as cursor:
                cursor.execute("SELECT 1")
            raise CommandError(
                f"Could not read contested snapshots: {exc}"
            ) from exc
