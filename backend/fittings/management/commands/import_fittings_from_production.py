"""
Copy EveFitting catalog data from production_readonly into the local default
database.

Imports fittings (including soft-deleted), tags, pods, refits, version history,
module substitutions, doctrines, and doctrine↔fitting links. Writes only to
default; never writes to production_readonly.

Does not import fitting/doctrine change requests (user FKs / approval state).

Usage (from backend/, with DB_READONLY_* / production_readonly configured):

    pipenv run python manage.py import_fittings_from_production --clear
    pipenv run python manage.py import_fittings_from_production --dry-run
    pipenv run python manage.py import_fittings_from_production

Options:
    --clear     Hard-delete local fittings/pods and related rows before import.
                Also clears FittingBuyOrder lines (PROTECT) and cascades market
                fitting/contract expectations that reference fittings.
    --dry-run   Validate and report counts without writing to default.
    --source    Database alias to read from (default: production_readonly).
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from safedelete.config import HARD_DELETE

from eveonline.helpers.production_import import (
    assert_local_has_eve_types,
    validate_source_alias,
)
from eveonline.models import EveLocation
from fittings.models import (
    EveDoctrine,
    EveDoctrineFitting,
    EveFitting,
    EveFittingChangeRequest,
    EveFittingHistory,
    EveFittingModuleSubstitution,
    EveFittingPod,
    EveFittingRefit,
    EveFittingTag,
    FittingTag,
)
from market.models.fitting_buy_order import (
    FittingBuyOrder,
    FittingBuyOrderLine,
)

LOCATION_SKIP_COPY = frozenset(
    {"location_id", "deleted", "deleted_by_cascade"}
)
# Preserve soft-delete flags from production when copying fittings/pods.
FITTING_SKIP_COPY = frozenset({"id"})
POD_SKIP_COPY = frozenset({"id"})
DOCTRINE_SKIP_COPY = frozenset({"id"})
REFIT_SKIP_COPY = frozenset({"id", "base_fitting"})
HISTORY_SKIP_COPY = frozenset({"id", "fitting"})
SUBSTITUTION_SKIP_COPY = frozenset({"id", "fitting"})


class Command(BaseCommand):
    help = (
        "Import EveFitting catalog (and related doctrines/pods/refits) "
        "from production_readonly into the local default database."
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
            help=(
                "Hard-delete local fittings/pods and related catalog rows "
                "before import."
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
        validate_source_alias(source, local)

        prod_fittings = list(
            EveFitting.all_objects.using(source).order_by("pk")
        )
        prod_pods = list(
            EveFittingPod.all_objects.using(source).order_by("pk")
        )
        prod_tags = list(EveFittingTag.objects.using(source).order_by("pk"))
        prod_refits = list(
            EveFittingRefit.objects.using(source).order_by("pk")
        )
        prod_history = list(
            EveFittingHistory.objects.using(source).order_by("pk")
        )
        prod_subs = list(
            EveFittingModuleSubstitution.objects.using(source)
            .select_related("preferred_module", "substitute_module")
            .order_by("pk")
        )
        prod_doctrines = list(EveDoctrine.objects.using(source).order_by("pk"))
        prod_doctrine_fittings = list(
            EveDoctrineFitting.objects.using(source).order_by("pk")
        )

        tag_through = list(
            EveFitting.tags.through.objects.using(source).order_by("pk")
        )
        pod_through = list(
            EveFitting.pods.through.objects.using(source).order_by("pk")
        )
        escape_through = list(
            EveFittingPod.escape_frigate_fittings.through.objects.using(
                source
            ).order_by("pk")
        )
        doctrine_loc_through = list(
            EveDoctrine.locations.through.objects.using(source).order_by("pk")
        )

        type_ids = {
            s.preferred_module_id for s in prod_subs if s.preferred_module_id
        } | {
            s.substitute_module_id for s in prod_subs if s.substitute_module_id
        }
        assert_local_has_eve_types(
            type_ids,
            local,
            hint="Load eveuniverse data locally first (eveuniverse_load_types).",
        )

        loc_ids = {row.evelocation_id for row in doctrine_loc_through}

        active = sum(1 for f in prod_fittings if f.deleted is None)
        deleted = len(prod_fittings) - active
        self.stdout.write(
            f"Source={source}: "
            f"{len(prod_fittings)} fittings ({active} active, {deleted} soft-deleted), "
            f"{len(prod_pods)} pods, {len(prod_tags)} tags, "
            f"{len(prod_refits)} refits, {len(prod_history)} history, "
            f"{len(prod_subs)} substitutions, "
            f"{len(prod_doctrines)} doctrines, "
            f"{len(prod_doctrine_fittings)} doctrine fittings."
        )
        self.stdout.write(
            f"M2M: {len(tag_through)} fitting↔tags, "
            f"{len(pod_through)} fitting↔pods, "
            f"{len(escape_through)} pod↔escape fittings, "
            f"{len(doctrine_loc_through)} doctrine↔locations."
        )
        if options["clear"]:
            self.stdout.write(
                self.style.WARNING(
                    "With --clear: local fittings/pods are hard-deleted; "
                    "FittingBuyOrder rows are removed (PROTECT); market "
                    "fitting/contract expectations that reference fittings "
                    "cascade away (re-run sync_market_expectations_from_production)."
                )
            )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        with transaction.atomic(using=local):
            if options["clear"]:
                self._clear_local(local)

            self._ensure_tag_vocabulary(local)
            prod_tag_pk_to_local = self._sync_tags(prod_tags, local)

            for lid in sorted(loc_ids):
                self._ensure_location(lid, source, local)

            for fitting in prod_fittings:
                self._upsert_fitting(fitting, local)

            for pod in prod_pods:
                self._upsert_pod(pod, local)

            for doctrine in prod_doctrines:
                self._upsert_doctrine(doctrine, local)

            self._replace_refits(prod_refits, local)
            self._replace_history(prod_history, local)
            self._replace_substitutions(prod_subs, local)
            self._replace_doctrine_fittings(prod_doctrine_fittings, local)

            self._sync_fitting_tags(tag_through, prod_tag_pk_to_local, local)
            self._sync_fitting_pods(pod_through, local)
            self._sync_escape_frigates(escape_through, local)
            self._sync_doctrine_locations(doctrine_loc_through, local)

            if options["clear"]:
                self._remove_local_only_doctrines(
                    {d.pk for d in prod_doctrines}, local
                )

        self._report_totals(local, source)

    def _clear_local(self, local: str) -> None:
        buy_lines, _ = FittingBuyOrderLine.objects.using(local).all().delete()
        buy_orders, _ = FittingBuyOrder.objects.using(local).all().delete()
        self.stdout.write(
            self.style.WARNING(
                f"Cleared FittingBuyOrderLine ({buy_lines}) and "
                f"FittingBuyOrder ({buy_orders})."
            )
        )

        EveDoctrineFitting.objects.using(local).all().delete()
        EveFittingModuleSubstitution.objects.using(local).all().delete()
        EveFittingRefit.objects.using(local).all().delete()
        EveFittingHistory.objects.using(local).all().delete()
        EveFitting.tags.through.objects.using(local).all().delete()
        EveFitting.pods.through.objects.using(local).all().delete()
        EveFittingPod.escape_frigate_fittings.through.objects.using(
            local
        ).all().delete()
        EveDoctrine.locations.through.objects.using(local).all().delete()
        EveFittingChangeRequest.objects.using(local).all().delete()

        fit_deleted, fit_detail = (
            EveFitting.all_objects.using(local)
            .all()
            .delete(force_policy=HARD_DELETE)
        )
        pod_deleted, pod_detail = (
            EveFittingPod.all_objects.using(local)
            .all()
            .delete(force_policy=HARD_DELETE)
        )
        self.stdout.write(
            self.style.WARNING(
                f"Hard-deleted local fittings ({fit_deleted} rows incl. cascades: "
                f"{fit_detail}) and pods ({pod_deleted}: {pod_detail})."
            )
        )

    def _ensure_tag_vocabulary(self, local: str) -> None:
        for slug, label in FittingTag.choices:
            EveFittingTag.objects.using(local).get_or_create(
                slug=slug,
                defaults={"label": label},
            )

    def _sync_tags(self, prod_tags, local: str) -> dict[int, int]:
        """Return map of production EveFittingTag pk → local pk (by slug)."""
        mapping: dict[int, int] = {}
        for tag in prod_tags:
            local_tag, _ = EveFittingTag.objects.using(local).get_or_create(
                slug=tag.slug,
                defaults={"label": tag.label},
            )
            if local_tag.label != tag.label:
                EveFittingTag.objects.using(local).filter(
                    pk=local_tag.pk
                ).update(label=tag.label)
            mapping[tag.pk] = local_tag.pk
        return mapping

    def _ensure_location(self, location_id, source, local):
        existing = (
            EveLocation.all_objects.using(local).filter(pk=location_id).first()
        )
        loc = (
            EveLocation.all_objects.using(source)
            .filter(pk=location_id)
            .first()
        )
        if loc is None:
            raise CommandError(
                f"EveLocation pk={location_id} missing on source={source}."
            )
        fields = {
            field.name: getattr(loc, field.name)
            for field in EveLocation._meta.concrete_fields  # pylint: disable=protected-access
            if field.name not in LOCATION_SKIP_COPY
        }
        if existing:
            EveLocation.all_objects.using(local).filter(pk=location_id).update(
                **fields,
                deleted=None,
                deleted_by_cascade=False,
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

    def _upsert_fitting(self, prod: EveFitting, local: str) -> None:
        fields = {
            field.name: getattr(prod, field.name)
            for field in EveFitting._meta.concrete_fields  # pylint: disable=protected-access
            if field.name not in FITTING_SKIP_COPY
        }
        existing = (
            EveFitting.all_objects.using(local).filter(pk=prod.pk).first()
        )
        if existing:
            EveFitting.all_objects.using(local).filter(pk=prod.pk).update(
                **fields
            )
            return
        EveFitting.all_objects.using(local).bulk_create(
            [EveFitting(id=prod.pk, **fields)]
        )

    def _upsert_pod(self, prod: EveFittingPod, local: str) -> None:
        fields = {
            field.name: getattr(prod, field.name)
            for field in EveFittingPod._meta.concrete_fields  # pylint: disable=protected-access
            if field.name not in POD_SKIP_COPY
        }
        existing = (
            EveFittingPod.all_objects.using(local).filter(pk=prod.pk).first()
        )
        if existing:
            EveFittingPod.all_objects.using(local).filter(pk=prod.pk).update(
                **fields
            )
            return
        EveFittingPod.all_objects.using(local).bulk_create(
            [EveFittingPod(id=prod.pk, **fields)]
        )

    def _upsert_doctrine(self, prod: EveDoctrine, local: str) -> None:
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

    def _replace_refits(self, prod_refits, local: str) -> None:
        EveFittingRefit.objects.using(local).all().delete()
        if not prod_refits:
            return
        EveFittingRefit.objects.using(local).bulk_create(
            [
                EveFittingRefit(
                    id=refit.pk,
                    base_fitting_id=refit.base_fitting_id,
                    **{
                        field.name: getattr(refit, field.name)
                        for field in EveFittingRefit._meta.concrete_fields  # pylint: disable=protected-access
                        if field.name not in REFIT_SKIP_COPY
                    },
                )
                for refit in prod_refits
            ]
        )

    def _replace_history(self, prod_history, local: str) -> None:
        EveFittingHistory.objects.using(local).all().delete()
        if not prod_history:
            return
        EveFittingHistory.objects.using(local).bulk_create(
            [
                EveFittingHistory(
                    id=row.pk,
                    fitting_id=row.fitting_id,
                    **{
                        field.name: getattr(row, field.name)
                        for field in EveFittingHistory._meta.concrete_fields  # pylint: disable=protected-access
                        if field.name not in HISTORY_SKIP_COPY
                    },
                )
                for row in prod_history
            ],
            batch_size=500,
        )

    def _replace_substitutions(self, prod_subs, local: str) -> None:
        EveFittingModuleSubstitution.objects.using(local).all().delete()
        if not prod_subs:
            return
        EveFittingModuleSubstitution.objects.using(local).bulk_create(
            [
                EveFittingModuleSubstitution(
                    id=row.pk,
                    fitting_id=row.fitting_id,
                    **{
                        field.name: getattr(row, field.name)
                        for field in EveFittingModuleSubstitution._meta.concrete_fields  # pylint: disable=protected-access
                        if field.name not in SUBSTITUTION_SKIP_COPY
                    },
                )
                for row in prod_subs
            ]
        )

    def _remove_local_only_doctrines(
        self, prod_doctrine_ids: set[int], local: str
    ) -> None:
        """Drop doctrines that exist only locally (no production PK)."""
        qs = EveDoctrine.objects.using(local).exclude(pk__in=prod_doctrine_ids)
        names = list(qs.values_list("pk", "name"))
        if not names:
            return
        deleted, _ = qs.delete()
        self.stdout.write(
            self.style.WARNING(
                f"Removed {deleted} local-only doctrine(s): {names}"
            )
        )

    def _replace_doctrine_fittings(self, prod_rows, local: str) -> None:
        EveDoctrineFitting.objects.using(local).all().delete()
        if not prod_rows:
            return
        EveDoctrineFitting.objects.using(local).bulk_create(
            [
                EveDoctrineFitting(
                    id=row.pk,
                    doctrine_id=row.doctrine_id,
                    fitting_id=row.fitting_id,
                    role=row.role,
                )
                for row in prod_rows
            ]
        )

    def _sync_fitting_tags(
        self, tag_through, prod_tag_pk_to_local, local: str
    ) -> None:
        EveFitting.tags.through.objects.using(local).all().delete()
        if not tag_through:
            return
        through_model = EveFitting.tags.through
        through_model.objects.using(local).bulk_create(
            [
                through_model(
                    evefitting_id=row.evefitting_id,
                    evefittingtag_id=prod_tag_pk_to_local[
                        row.evefittingtag_id
                    ],
                )
                for row in tag_through
            ],
            batch_size=500,
        )

    def _sync_fitting_pods(self, pod_through, local: str) -> None:
        EveFitting.pods.through.objects.using(local).all().delete()
        if not pod_through:
            return
        through_model = EveFitting.pods.through
        through_model.objects.using(local).bulk_create(
            [
                through_model(
                    evefitting_id=row.evefitting_id,
                    evefittingpod_id=row.evefittingpod_id,
                )
                for row in pod_through
            ],
            batch_size=500,
        )

    def _sync_escape_frigates(self, escape_through, local: str) -> None:
        EveFittingPod.escape_frigate_fittings.through.objects.using(
            local
        ).all().delete()
        if not escape_through:
            return
        through_model = EveFittingPod.escape_frigate_fittings.through
        through_model.objects.using(local).bulk_create(
            [
                through_model(
                    evefittingpod_id=row.evefittingpod_id,
                    evefitting_id=row.evefitting_id,
                )
                for row in escape_through
            ]
        )

    def _sync_doctrine_locations(
        self, doctrine_loc_through, local: str
    ) -> None:
        EveDoctrine.locations.through.objects.using(local).all().delete()
        if not doctrine_loc_through:
            return
        through_model = EveDoctrine.locations.through
        through_model.objects.using(local).bulk_create(
            [
                through_model(
                    evedoctrine_id=row.evedoctrine_id,
                    evelocation_id=row.evelocation_id,
                )
                for row in doctrine_loc_through
            ]
        )

    def _report_totals(self, local: str, source: str) -> None:
        def counts(alias):
            return {
                "fittings_all": EveFitting.all_objects.using(alias).count(),
                "fittings_active": EveFitting.objects.using(alias).count(),
                "pods": EveFittingPod.all_objects.using(alias).count(),
                "refits": EveFittingRefit.objects.using(alias).count(),
                "history": EveFittingHistory.objects.using(alias).count(),
                "subs": EveFittingModuleSubstitution.objects.using(
                    alias
                ).count(),
                "doctrines": EveDoctrine.objects.using(alias).count(),
                "doctrine_fits": EveDoctrineFitting.objects.using(
                    alias
                ).count(),
                "tag_links": EveFitting.tags.through.objects.using(
                    alias
                ).count(),
                "pod_links": EveFitting.pods.through.objects.using(
                    alias
                ).count(),
            }

        local_counts = counts(local)
        prod_counts = counts(source)
        self.stdout.write(
            self.style.SUCCESS(f"Imported into {local}: {local_counts}")
        )
        self.stdout.write(f"Production totals: {prod_counts}")
        mismatches = [
            key
            for key in (
                "fittings_all",
                "fittings_active",
                "pods",
                "refits",
                "history",
                "subs",
                "doctrine_fits",
                "tag_links",
                "pod_links",
            )
            if local_counts[key] != prod_counts[key]
        ]
        if mismatches:
            self.stdout.write(
                self.style.WARNING(
                    f"Count mismatches vs source (expected if local-only "
                    f"doctrines remain): {mismatches}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Catalog counts match production for fittings-related tables."
                )
            )

        sample = (
            EveFitting.objects.using(local)
            .prefetch_related("tags", "pods", "refits")
            .order_by("pk")
            .first()
        )
        if sample:
            prod = EveFitting.all_objects.using(source).get(pk=sample.pk)
            self.stdout.write(
                f"Sample fitting pk={sample.pk} name={sample.name!r} "
                f"ship_id={sample.ship_id} eft_len={len(sample.eft_format or '')} "
                f"tags={sample.tag_slugs()} "
                f"pods={sample.pods.count()} refits={sample.refits.count()} "
                f"eft_match={sample.eft_format == prod.eft_format}."
            )
