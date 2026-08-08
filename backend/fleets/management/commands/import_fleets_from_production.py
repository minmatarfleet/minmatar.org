"""
Copy recent doctrine fleets (instances + members) from production_readonly
into the local default database for Market “fleets remaining” comps.

Also syncs EveDoctrine / EveDoctrineFitting / missing EveFitting rows and
referenced EveLocation / EveFleetAudience rows. Writes only to default.

Discord fleet-schedule signals are disconnected during import.

Usage (from backend/, with DB_READONLY_* / production_readonly configured):

    pipenv run python manage.py import_fleets_from_production
    pipenv run python manage.py import_fleets_from_production --days 90
    pipenv run python manage.py import_fleets_from_production --clear --dry-run
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import signals
from django.utils import timezone

from eveonline.models import EveLocation
from fittings.models import EveDoctrine, EveDoctrineFitting, EveFitting
from fleets.models import (
    EveFleet,
    EveFleetAudience,
    EveFleetInstance,
    EveFleetInstanceMember,
    EveFleetInstanceMemberShipSnapshot,
)
from fleets.signals import (
    update_fleet_schedule_on_delete,
    update_fleet_schedule_on_save,
)

LOCATION_SKIP_COPY = frozenset(
    {"location_id", "deleted", "deleted_by_cascade"}
)
FITTING_SKIP_COPY = frozenset({"id", "deleted", "deleted_by_cascade"})
DOCTRINE_SKIP_COPY = frozenset({"id"})
AUDIENCE_SKIP_COPY = frozenset({"id"})
FLEET_SKIP_COPY = frozenset({"id", "created_by"})
INSTANCE_SKIP_COPY = frozenset({"id", "eve_fleet"})
MEMBER_SKIP_COPY = frozenset({"id", "eve_fleet_instance"})
SNAPSHOT_SKIP_COPY = frozenset({"id", "member"})


class Command(BaseCommand):
    help = (
        "Import doctrine fleets + members from production_readonly "
        "into the local default database (for fleets-remaining comps)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="production_readonly",
            help="Django DB alias to read from (default: production_readonly).",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=90,
            help="Import fleets with start_time within this many days.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help=(
                "Before import, delete local fleets (cascade instances/members) "
                "in the same start_time window that have a doctrine."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not write; only validate and print planned counts.",
        )

    def handle(self, *args, **options):
        source = options["source"]
        local = "default"
        days = options["days"]
        self._validate_aliases(source, local)
        if days < 1:
            raise CommandError("--days must be >= 1.")

        cutoff = timezone.now() - timedelta(days=days)
        doctrines = list(EveDoctrine.objects.using(source).order_by("pk"))
        doctrine_fittings = list(
            EveDoctrineFitting.objects.using(source)
            .select_related("fitting", "doctrine")
            .order_by("pk")
        )
        fleets = list(
            EveFleet.objects.using(source)
            .filter(start_time__gte=cutoff, doctrine_id__isnull=False)
            .order_by("pk")
        )
        fleet_ids = [f.pk for f in fleets]
        instances = list(
            EveFleetInstance.objects.using(source)
            .filter(eve_fleet_id__in=fleet_ids)
            .order_by("pk")
        )
        instance_ids = [i.pk for i in instances]
        members = list(
            EveFleetInstanceMember.objects.using(source)
            .filter(eve_fleet_instance_id__in=instance_ids)
            .order_by("pk")
        )
        member_ids = [m.pk for m in members]
        ship_snapshots = list(
            EveFleetInstanceMemberShipSnapshot.objects.using(source)
            .filter(member_id__in=member_ids)
            .order_by("pk")
        )

        fit_ids = {df.fitting_id for df in doctrine_fittings}
        loc_ids = {f.location_id for f in fleets if f.location_id} | {
            a.staging_location_id
            for a in EveFleetAudience.objects.using(source).all()
            if a.staging_location_id
        }
        audience_ids = {f.audience_id for f in fleets if f.audience_id}
        audiences = list(
            EveFleetAudience.objects.using(source)
            .filter(pk__in=audience_ids)
            .order_by("pk")
        )

        self.stdout.write(
            f"Source={source} days={days}: "
            f"{len(doctrines)} doctrines, "
            f"{len(doctrine_fittings)} doctrine fittings, "
            f"{len(fleets)} doctrine fleets, "
            f"{len(instances)} instances, "
            f"{len(members)} members, "
            f"{len(ship_snapshots)} ship snapshots."
        )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        signals.post_save.disconnect(
            update_fleet_schedule_on_save,
            sender=EveFleet,
            dispatch_uid="update_fleet_schedule_on_save",
        )
        signals.post_delete.disconnect(
            update_fleet_schedule_on_delete,
            sender=EveFleet,
        )
        try:
            with transaction.atomic(using=local):
                if options["clear"]:
                    deleted, _ = (
                        EveFleet.objects.using(local)
                        .filter(
                            start_time__gte=cutoff,
                            doctrine_id__isnull=False,
                        )
                        .delete()
                    )
                    self.stdout.write(
                        self.style.WARNING(
                            f"Cleared local doctrine fleets in window ({deleted})."
                        )
                    )

                for lid in sorted(loc_ids):
                    self._ensure_location(lid, source, local)

                for fid in sorted(fit_ids):
                    self._ensure_fitting(fid, source, local)

                for doctrine in doctrines:
                    self._upsert_doctrine(doctrine, local)

                # Replace doctrine fittings for imported doctrines.
                doctrine_ids = [d.pk for d in doctrines]
                EveDoctrineFitting.objects.using(local).filter(
                    doctrine_id__in=doctrine_ids
                ).delete()
                EveDoctrineFitting.objects.using(local).bulk_create(
                    [
                        EveDoctrineFitting(
                            id=df.pk,
                            doctrine_id=df.doctrine_id,
                            fitting_id=df.fitting_id,
                            role=df.role,
                        )
                        for df in doctrine_fittings
                    ]
                )
                self.stdout.write(
                    f"  Synced {len(doctrine_fittings)} doctrine fittings."
                )

                for audience in audiences:
                    self._upsert_audience(audience, source, local)

                for fleet in fleets:
                    self._upsert_fleet(fleet, local)

                # Replace instances/members for imported fleets.
                EveFleetInstance.objects.using(local).filter(
                    eve_fleet_id__in=fleet_ids
                ).delete()
                EveFleetInstance.objects.using(local).bulk_create(
                    [
                        EveFleetInstance(
                            id=inst.pk,
                            eve_fleet_id=inst.eve_fleet_id,
                            **{
                                field.name: getattr(inst, field.name)
                                for field in EveFleetInstance._meta.concrete_fields  # pylint: disable=protected-access
                                if field.name not in INSTANCE_SKIP_COPY
                            },
                        )
                        for inst in instances
                    ]
                )
                EveFleetInstanceMember.objects.using(local).bulk_create(
                    [
                        EveFleetInstanceMember(
                            id=member.pk,
                            eve_fleet_instance_id=member.eve_fleet_instance_id,
                            **{
                                field.name: getattr(member, field.name)
                                for field in EveFleetInstanceMember._meta.concrete_fields  # pylint: disable=protected-access
                                if field.name not in MEMBER_SKIP_COPY
                            },
                        )
                        for member in members
                    ],
                    batch_size=500,
                )
                EveFleetInstanceMemberShipSnapshot.objects.using(local).filter(
                    member_id__in=member_ids
                ).delete()
                EveFleetInstanceMemberShipSnapshot.objects.using(
                    local
                ).bulk_create(
                    [
                        EveFleetInstanceMemberShipSnapshot(
                            id=snap.pk,
                            member_id=snap.member_id,
                            **{
                                field.name: getattr(snap, field.name)
                                for field in EveFleetInstanceMemberShipSnapshot._meta.concrete_fields  # pylint: disable=protected-access
                                if field.name not in SNAPSHOT_SKIP_COPY
                            },
                        )
                        for snap in ship_snapshots
                    ],
                    batch_size=1000,
                )
        finally:
            signals.post_save.connect(
                update_fleet_schedule_on_save,
                sender=EveFleet,
                dispatch_uid="update_fleet_schedule_on_save",
            )
            signals.post_delete.connect(
                update_fleet_schedule_on_delete,
                sender=EveFleet,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported into {local}: "
                f"{EveFleet.objects.using(local).filter(start_time__gte=cutoff, doctrine_id__isnull=False).count()} "
                f"doctrine fleets, "
                f"{EveFleetInstance.objects.using(local).filter(eve_fleet_id__in=fleet_ids).count()} instances, "
                f"{EveFleetInstanceMember.objects.using(local).filter(eve_fleet_instance_id__in=instance_ids).count()} members, "
                f"{EveFleetInstanceMemberShipSnapshot.objects.using(local).filter(member_id__in=member_ids).count()} ship snapshots."
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

    def _ensure_location(self, location_id, source, local):
        existing = (
            EveLocation.all_objects.using(local).filter(pk=location_id).first()
        )
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
                existing.staging_active = False
                existing.save(using=local)
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

    def _ensure_fitting(self, fitting_id, source, local):
        existing = (
            EveFitting.all_objects.using(local).filter(pk=fitting_id).first()
        )
        prod = (
            EveFitting.all_objects.using(source).filter(pk=fitting_id).first()
        )
        if prod is None:
            raise CommandError(
                f"EveFitting pk={fitting_id} missing on source={source}."
            )
        fields = {
            field.name: getattr(prod, field.name)
            for field in EveFitting._meta.concrete_fields  # pylint: disable=protected-access
            if field.name not in FITTING_SKIP_COPY
        }
        if existing:
            EveFitting.all_objects.using(local).filter(pk=fitting_id).update(
                **fields,
                deleted=None,
                deleted_by_cascade=False,
            )
            return
        obj = EveFitting(id=fitting_id, **fields)
        EveFitting.all_objects.using(local).bulk_create([obj])
        self.stdout.write(f"  Copied EveFitting {fitting_id} ({prod.name}).")

    def _upsert_doctrine(self, prod, local):
        fields = {
            field.name: getattr(prod, field.name)
            for field in EveDoctrine._meta.concrete_fields  # pylint: disable=protected-access
            if field.name not in DOCTRINE_SKIP_COPY
        }
        existing = EveDoctrine.objects.using(local).filter(pk=prod.pk).first()
        if existing:
            EveDoctrine.objects.using(local).filter(pk=prod.pk).update(
                **fields
            )
            return
        EveDoctrine.objects.using(local).bulk_create(
            [EveDoctrine(id=prod.pk, **fields)]
        )
        self.stdout.write(f"  Copied EveDoctrine {prod.pk} ({prod.name}).")

    def _upsert_audience(self, prod, source, local):
        if prod.staging_location_id:
            self._ensure_location(prod.staging_location_id, source, local)
        fields = {
            field.name: getattr(prod, field.name)
            for field in EveFleetAudience._meta.concrete_fields  # pylint: disable=protected-access
            if field.name not in AUDIENCE_SKIP_COPY
        }
        # Avoid Discord schedule side effects if anything re-saves later.
        fields["add_to_schedule"] = False
        existing = (
            EveFleetAudience.objects.using(local).filter(pk=prod.pk).first()
        )
        if existing:
            EveFleetAudience.objects.using(local).filter(pk=prod.pk).update(
                **fields
            )
            return
        EveFleetAudience.objects.using(local).bulk_create(
            [EveFleetAudience(id=prod.pk, **fields)]
        )
        self.stdout.write(
            f"  Copied EveFleetAudience {prod.pk} ({prod.name})."
        )

    def _upsert_fleet(self, prod, local):
        fields = {
            field.name: getattr(prod, field.name)
            for field in EveFleet._meta.concrete_fields  # pylint: disable=protected-access
            if field.name not in FLEET_SKIP_COPY
        }
        # Avoid missing User FKs and Discord schedule work.
        fields["created_by_id"] = None
        existing = EveFleet.objects.using(local).filter(pk=prod.pk).first()
        if existing:
            EveFleet.objects.using(local).filter(pk=prod.pk).update(**fields)
            return
        EveFleet.objects.using(local).bulk_create(
            [EveFleet(id=prod.pk, **fields)]
        )
