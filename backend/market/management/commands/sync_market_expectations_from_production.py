"""
Copy market contract / fitting / item / buy-order expectations from
production_readonly into the local default database.

Also copies any missing EveFitting rows (by primary key) and ensures
referenced EveLocation rows exist. Writes only to default.

Usage (from backend/, with DB_READONLY_* / production_readonly configured):

    pipenv run python manage.py sync_market_expectations_from_production
    pipenv run python manage.py sync_market_expectations_from_production --clear
    pipenv run python manage.py sync_market_expectations_from_production --dry-run
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from eveonline.models import EveLocation
from fittings.models import EveFitting
from market.models import (
    EveMarketBuyOrderExpectation,
    EveMarketContractExpectation,
    EveMarketFittingExpectation,
    EveMarketItemExpectation,
)

LOCATION_SKIP_COPY = frozenset(
    {"location_id", "deleted", "deleted_by_cascade"}
)
FITTING_SKIP_COPY = frozenset({"id", "deleted", "deleted_by_cascade"})


class Command(BaseCommand):
    help = (
        "Sync market expectations (contract, fitting, item, buy-order) "
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
            help="Remove local expectation rows before import.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not write; only validate and print planned work.",
        )

    def handle(self, *args, **options):  # noqa: C901
        source = options["source"]
        local = "default"
        self._validate_aliases(source, local)

        contract_exps = list(
            EveMarketContractExpectation.objects.using(source)
            .select_related("fitting", "location")
            .order_by("pk")
        )
        fitting_exps = list(
            EveMarketFittingExpectation.objects.using(source)
            .select_related("fitting", "location")
            .order_by("pk")
        )
        item_exps = list(
            EveMarketItemExpectation.objects.using(source)
            .select_related("item", "location")
            .order_by("pk")
        )
        buy_exps = list(
            EveMarketBuyOrderExpectation.objects.using(source)
            .select_related("item", "location")
            .order_by("pk")
        )

        fit_ids = {e.fitting_id for e in contract_exps} | {
            e.fitting_id for e in fitting_exps
        }
        loc_ids = (
            {e.location_id for e in contract_exps}
            | {e.location_id for e in fitting_exps}
            | {e.location_id for e in item_exps}
            | {e.location_id for e in buy_exps}
        )
        item_ids = {e.item_id for e in item_exps} | {
            e.item_id for e in buy_exps
        }

        missing_fit_ids = self._missing_fitting_ids(fit_ids, local)
        missing_loc_ids = self._missing_location_ids(loc_ids, local)

        self.stdout.write(
            f"Source={source}: "
            f"{len(contract_exps)} contract expectations, "
            f"{len(fitting_exps)} fitting expectations, "
            f"{len(item_exps)} item expectations, "
            f"{len(buy_exps)} buy-order expectations."
        )
        self.stdout.write(
            f"Dependencies: {len(fit_ids)} fittings "
            f"({len(missing_fit_ids)} missing locally), "
            f"{len(loc_ids)} locations "
            f"({len(missing_loc_ids)} missing locally), "
            f"{len(item_ids)} EveTypes."
        )

        if options["dry_run"]:
            if missing_fit_ids:
                self.stdout.write(
                    f"Would copy EveFitting ids: {sorted(missing_fit_ids)}"
                )
            if missing_loc_ids:
                self.stdout.write(
                    f"Would copy EveLocation ids: {sorted(missing_loc_ids)}"
                )
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        with transaction.atomic(using=local):
            if options["clear"]:
                for model, label in (
                    (EveMarketContractExpectation, "contract expectations"),
                    (EveMarketFittingExpectation, "fitting expectations"),
                    (EveMarketItemExpectation, "item expectations"),
                    (EveMarketBuyOrderExpectation, "buy-order expectations"),
                ):
                    deleted, _ = model.objects.using(local).all().delete()
                    self.stdout.write(
                        self.style.WARNING(
                            f"Cleared local {label} ({deleted})."
                        )
                    )

            for lid in sorted(loc_ids):
                self._ensure_location(lid, source, local)

            for fid in sorted(fit_ids):
                self._ensure_fitting(fid, source, local)

            c_created = c_updated = 0
            for exp in contract_exps:
                if self._upsert_contract_expectation(exp, local):
                    c_created += 1
                else:
                    c_updated += 1

            f_created = f_updated = 0
            for exp in fitting_exps:
                if self._upsert_fitting_expectation(exp, local):
                    f_created += 1
                else:
                    f_updated += 1

            i_created = i_updated = 0
            for exp in item_exps:
                if self._upsert_item_expectation(exp, local):
                    i_created += 1
                else:
                    i_updated += 1

            b_created = b_updated = 0
            for exp in buy_exps:
                if self._upsert_buy_expectation(exp, local):
                    b_created += 1
                else:
                    b_updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Synced into {local}: "
                f"contract {c_created}+{c_updated}, "
                f"fitting {f_created}+{f_updated}, "
                f"item {i_created}+{i_updated}, "
                f"buy {b_created}+{b_updated} "
                f"(created+updated)."
            )
        )
        self.stdout.write(
            "Local totals: "
            f"contract={EveMarketContractExpectation.objects.using(local).count()}, "
            f"fitting={EveMarketFittingExpectation.objects.using(local).count()}, "
            f"item={EveMarketItemExpectation.objects.using(local).count()}, "
            f"buy={EveMarketBuyOrderExpectation.objects.using(local).count()}."
        )

    def _validate_aliases(self, source, local):
        if source not in settings.DATABASES:
            raise CommandError(
                f'Database alias "{source}" is not configured. '
                "Set production_readonly (see app settings / DB_READONLY_*)."
            )
        if source == local:
            raise CommandError("Source and destination must differ.")

    def _missing_fitting_ids(self, fit_ids, local):
        present = set(
            EveFitting.all_objects.using(local)
            .filter(pk__in=fit_ids)
            .values_list("pk", flat=True)
        )
        return fit_ids - present

    def _missing_location_ids(self, loc_ids, local):
        present = set(
            EveLocation.all_objects.using(local)
            .filter(pk__in=loc_ids)
            .values_list("pk", flat=True)
        )
        return loc_ids - present

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
                existing.save(using=local)
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
            for key, value in fields.items():
                setattr(existing, key, value)
            existing.deleted = None
            existing.deleted_by_cascade = False
            # Bypass versioning side effects for sync.
            EveFitting.all_objects.using(local).filter(pk=fitting_id).update(
                **fields,
                deleted=None,
                deleted_by_cascade=False,
            )
            return False

        # Preserve production PK so expectation FKs match.
        obj = EveFitting(id=fitting_id, **fields)
        EveFitting.all_objects.using(local).bulk_create([obj])
        self.stdout.write(f"  Copied EveFitting {fitting_id} ({prod.name}).")
        return True

    def _upsert_contract_expectation(self, prod_exp, local):
        existing = (
            EveMarketContractExpectation.objects.using(local)
            .filter(
                fitting_id=prod_exp.fitting_id,
                location_id=prod_exp.location_id,
            )
            .first()
        )
        if existing:
            existing.quantity = prod_exp.quantity
            existing.save(using=local)
            return False
        EveMarketContractExpectation.objects.using(local).create(
            fitting_id=prod_exp.fitting_id,
            location_id=prod_exp.location_id,
            quantity=prod_exp.quantity,
        )
        return True

    def _upsert_fitting_expectation(self, prod_exp, local):
        existing = (
            EveMarketFittingExpectation.objects.using(local)
            .filter(
                fitting_id=prod_exp.fitting_id,
                location_id=prod_exp.location_id,
            )
            .first()
        )
        if existing:
            existing.quantity = prod_exp.quantity
            existing.save(using=local)
            return False
        EveMarketFittingExpectation.objects.using(local).create(
            fitting_id=prod_exp.fitting_id,
            location_id=prod_exp.location_id,
            quantity=prod_exp.quantity,
        )
        return True

    def _upsert_item_expectation(self, prod_exp, local):
        existing = (
            EveMarketItemExpectation.objects.using(local)
            .filter(
                item_id=prod_exp.item_id,
                location_id=prod_exp.location_id,
            )
            .first()
        )
        if existing:
            existing.quantity = prod_exp.quantity
            existing.save(using=local)
            return False
        EveMarketItemExpectation.objects.using(local).create(
            item_id=prod_exp.item_id,
            location_id=prod_exp.location_id,
            quantity=prod_exp.quantity,
        )
        return True

    def _upsert_buy_expectation(self, prod_exp, local):
        existing = (
            EveMarketBuyOrderExpectation.objects.using(local)
            .filter(
                item_id=prod_exp.item_id,
                location_id=prod_exp.location_id,
            )
            .first()
        )
        if existing:
            existing.quantity = prod_exp.quantity
            existing.save(using=local)
            return False
        EveMarketBuyOrderExpectation.objects.using(local).create(
            item_id=prod_exp.item_id,
            location_id=prod_exp.location_id,
            quantity=prod_exp.quantity,
        )
        return True
