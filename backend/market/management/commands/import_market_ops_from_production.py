"""
Copy market ops data from production_readonly into the local default database
so /market/ops/ matches production.

Imports (writes only to default):
  - Market expectations (delegates to sync_market_expectations_from_production)
  - EveMarketContract + EveMarketContractItem (outstanding by default)
  - EveMarketItemOrder
  - EveMarketInferredSale
  - EveMarketOrderBookSync
  - EveMarketItemLocationPrice
  - EveMarketItemHistory for ops-relevant types over the last N days

Usage (from backend/, with DB_READONLY_* configured):

    pipenv run python manage.py import_market_ops_from_production --clear
    pipenv run python manage.py import_market_ops_from_production --dry-run
    pipenv run python manage.py import_market_ops_from_production --clear --all-contracts
    pipenv run python manage.py import_market_ops_from_production --clear --history-days 30
"""

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db.models import QuerySet
from django.utils import timezone
from eveuniverse.models import EveType

from eveonline.models import EveLocation
from fittings.models import EveFitting
from market.helpers.contract_match import fitting_type_quantities_bulk
from market.models import (
    EveMarketContract,
    EveMarketContractItem,
    EveMarketInferredSale,
    EveMarketItemHistory,
    EveMarketItemLocationPrice,
    EveMarketItemOrder,
    EveMarketOrderBookSync,
)

LOCATION_SKIP_COPY = frozenset(
    {"location_id", "deleted", "deleted_by_cascade"}
)
FITTING_SKIP_COPY = frozenset({"id", "deleted", "deleted_by_cascade"})
BATCH = 5000


class Command(BaseCommand):
    help = (
        "Import market contracts, orders, inferred sales, prices, and recent "
        "history from production_readonly into the local default database."
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
                "Replace local contracts/orders/sales/sync/location-prices "
                "and re-sync expectations before import."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not write; only validate and print planned counts.",
        )
        parser.add_argument(
            "--history-days",
            type=int,
            default=90,
            help=(
                "Import EveMarketItemHistory rows with date >= now - N days "
                "for ops-relevant types (default: 90). Use 0 to skip history."
            ),
        )
        parser.add_argument(
            "--skip-expectations",
            action="store_true",
            help="Do not run sync_market_expectations_from_production.",
        )
        parser.add_argument(
            "--only-history",
            action="store_true",
            help=(
                "Only refresh EveMarketItemHistory (no clear of live tables). "
                "Still requires --clear to acknowledge writes."
            ),
        )
        parser.add_argument(
            "--all-contracts",
            action="store_true",
            help=(
                "Import every contract (including finished). Default is "
                "status=outstanding only — enough for /market/ops/."
            ),
        )

    def handle(self, *args, **options):
        source = options["source"]
        local = "default"
        history_days = options["history_days"]
        all_contracts = options["all_contracts"]
        self._validate_aliases(source, local)
        if history_days < 0:
            raise CommandError("--history-days must be >= 0.")

        contract_qs = self._contract_queryset(source, all_contracts)
        counts = self._source_counts(source, history_days, contract_qs)
        for label, n in counts.items():
            self.stdout.write(f"Source {label}: {n}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        if not options["clear"]:
            raise CommandError(
                "Refusing to import without --clear (avoids duplicate PK "
                "collisions on contracts/orders). Re-run with --clear."
            )

        if options["only_history"]:
            if history_days <= 0:
                raise CommandError(
                    "--only-history requires --history-days > 0."
                )
            fit_ids = set(
                EveMarketContract.objects.using(local)
                .exclude(fitting_id__isnull=True)
                .values_list("fitting_id", flat=True)
                .distinct()
            )
            contract_ids = list(
                EveMarketContract.objects.using(local).values_list(
                    "pk", flat=True
                )
            )
            # Resolve type IDs from local live tables + prod fittings EFT.
            history_type_ids = self._history_type_ids_local(
                local, source, fit_ids, contract_ids
            )
            self._import_history(source, local, history_days, history_type_ids)
            self.stdout.write(self.style.SUCCESS("History import complete."))
            self._write_local_totals(local)
            return

        if not options["skip_expectations"]:
            self.stdout.write("Syncing market expectations…")
            call_command(
                "sync_market_expectations_from_production",
                source=source,
                clear=True,
                verbosity=options.get("verbosity", 1),
            )

        contract_ids = list(contract_qs.values_list("pk", flat=True))
        loc_ids, fit_ids, type_ids = self._gather_dependency_ids(
            source, contract_ids
        )
        missing_types = self._missing_eve_type_ids(type_ids, local)
        if missing_types:
            self.stdout.write(
                f"Fetching {len(missing_types)} missing EveType(s) from ESI…"
            )
            self._fetch_missing_eve_types(missing_types)
            still_missing = self._missing_eve_type_ids(type_ids, local)
            if still_missing:
                raise CommandError(
                    "Local default DB is missing EveType rows for EVE type IDs: "
                    f"{still_missing[:20]}"
                    f"{'…' if len(still_missing) > 20 else ''}."
                )

        self._clear_live_tables(local)

        for lid in sorted(loc_ids):
            self._ensure_location(lid, source, local)
        for fid in sorted(fit_ids):
            self._ensure_fitting(fid, source, local)

        self._import_contracts(source, local, contract_ids)
        self._import_orders(source, local)
        self._import_inferred_sales(source, local)
        self._import_order_book_sync(source, local)
        self._import_location_prices(source, local)

        if history_days > 0:
            history_type_ids = self._history_type_ids(
                source, fit_ids, contract_ids
            )
            self._import_history(source, local, history_days, history_type_ids)

        self.stdout.write(self.style.SUCCESS("Market ops import complete."))
        self._write_local_totals(local)

    def _validate_aliases(self, source, local):
        if source not in settings.DATABASES:
            raise CommandError(
                f'Database alias "{source}" is not configured. '
                "Set production_readonly (see app settings / DB_READONLY_*)."
            )
        if source == local:
            raise CommandError("Source and destination must differ.")

    def _contract_queryset(self, source, all_contracts) -> QuerySet:
        qs = EveMarketContract.objects.using(source)
        if not all_contracts:
            qs = qs.filter(status="outstanding")
        return qs

    def _source_counts(self, source, history_days, contract_qs):
        contract_ids = contract_qs.values_list("pk", flat=True)
        counts = {
            "contracts": contract_qs.count(),
            "contract_items": EveMarketContractItem.objects.using(source)
            .filter(contract_id__in=contract_ids)
            .count(),
            "orders": EveMarketItemOrder.objects.using(source).count(),
            "inferred_sales": EveMarketInferredSale.objects.using(
                source
            ).count(),
            "order_book_syncs": EveMarketOrderBookSync.objects.using(
                source
            ).count(),
            "location_prices": EveMarketItemLocationPrice.objects.using(
                source
            ).count(),
        }
        if history_days > 0:
            counts[f"history_last_{history_days}d"] = "(ops types)"
        else:
            counts["history"] = 0
        return counts

    def _gather_dependency_ids(self, source, contract_ids):
        loc_ids = set(
            EveMarketContract.objects.using(source)
            .filter(pk__in=contract_ids)
            .exclude(location_id__isnull=True)
            .values_list("location_id", flat=True)
            .distinct()
        )
        loc_ids |= set(
            EveMarketItemOrder.objects.using(source)
            .values_list("location_id", flat=True)
            .distinct()
        )
        loc_ids |= set(
            EveMarketOrderBookSync.objects.using(source).values_list(
                "location_id", flat=True
            )
        )
        loc_ids |= set(
            EveMarketItemLocationPrice.objects.using(source)
            .values_list("location_id", flat=True)
            .distinct()
        )

        fit_ids = set(
            EveMarketContract.objects.using(source)
            .filter(pk__in=contract_ids)
            .exclude(fitting_id__isnull=True)
            .values_list("fitting_id", flat=True)
            .distinct()
        )

        type_ids = set(
            EveMarketItemOrder.objects.using(source)
            .values_list("item_id", flat=True)
            .distinct()
        )
        type_ids |= set(
            EveMarketItemLocationPrice.objects.using(source)
            .values_list("item_id", flat=True)
            .distinct()
        )
        type_ids |= set(
            EveMarketContractItem.objects.using(source)
            .filter(contract_id__in=contract_ids)
            .values_list("type_id", flat=True)
            .distinct()
        )
        return loc_ids, fit_ids, type_ids

    def _missing_eve_type_ids(self, type_ids, local):
        present = set(
            EveType.objects.using(local)
            .filter(pk__in=type_ids)
            .values_list("pk", flat=True)
        )
        return sorted(type_ids - present)

    def _fetch_missing_eve_types(self, type_ids):
        for tid in type_ids:
            EveType.objects.update_or_create_esi(
                id=tid, include_children=False
            )
            self.stdout.write(f"  EveType {tid}")

    def _history_type_ids(self, source, fit_ids, contract_ids):
        """Types needed for ops markup / viability baselines."""
        type_ids = set(
            EveMarketItemOrder.objects.using(source)
            .values_list("item_id", flat=True)
            .distinct()
        )
        type_ids |= set(
            EveMarketContractItem.objects.using(source)
            .filter(contract_id__in=contract_ids)
            .values_list("type_id", flat=True)
            .distinct()
        )
        fittings = list(
            EveFitting.all_objects.using(source).filter(pk__in=fit_ids)
        )
        for fit in fittings:
            type_ids.add(fit.ship_id)
        for qty_by_type in fitting_type_quantities_bulk(fittings).values():
            type_ids.update(qty_by_type.keys())
        return type_ids

    def _history_type_ids_local(self, local, source, fit_ids, contract_ids):
        type_ids = set(
            EveMarketItemOrder.objects.using(local)
            .values_list("item_id", flat=True)
            .distinct()
        )
        type_ids |= set(
            EveMarketContractItem.objects.using(local)
            .filter(contract_id__in=contract_ids)
            .values_list("type_id", flat=True)
            .distinct()
        )
        fittings = list(
            EveFitting.all_objects.using(source).filter(pk__in=fit_ids)
        )
        for fit in fittings:
            type_ids.add(fit.ship_id)
        for qty_by_type in fitting_type_quantities_bulk(fittings).values():
            type_ids.update(qty_by_type.keys())
        return type_ids

    def _clear_live_tables(self, local):
        for model, label in (
            (EveMarketInferredSale, "inferred sales"),
            (EveMarketItemOrder, "item orders"),
            (EveMarketContract, "contracts"),
            (EveMarketOrderBookSync, "order book syncs"),
            (EveMarketItemLocationPrice, "location prices"),
        ):
            deleted, _ = model.objects.using(local).all().delete()
            self.stdout.write(
                self.style.WARNING(f"Cleared local {label} ({deleted}).")
            )

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

    def _field_names(self, model, *, include_pk=True):
        # Use attname so FKs are location_id / item_id (ints), not related objects.
        names = [
            f.attname
            for f in model._meta.concrete_fields  # pylint: disable=protected-access
        ]
        if not include_pk:
            pk_attname = (
                model._meta.pk.attname
            )  # pylint: disable=protected-access
            names = [n for n in names if n != pk_attname]
        return names

    def _bulk_copy(
        self,
        *,
        model,
        source_qs,
        local,
        label,
        include_pk=True,
        ensure_item_fk=None,
        ensure_location_fk=None,
        source=None,
    ):
        """Keyset-paginate `.values()` from source and bulk_create locally."""
        self.stdout.write(f"Importing {label}…")
        pk_attname = model._meta.pk.attname  # pylint: disable=protected-access
        # Always select PK for keyset pagination; omit it on create when local
        # should allocate a new auto-id (child rows without cross-DB PK links).
        value_fields = self._field_names(model, include_pk=True)
        create_fields = (
            value_fields
            if include_pk
            else [n for n in value_fields if n != pk_attname]
        )
        last_pk = 0
        created = 0
        while True:
            filter_kwargs = {f"{pk_attname}__gt": last_pk} if last_pk else {}
            rows = list(
                source_qs.filter(**filter_kwargs)
                .order_by(pk_attname)
                .values(*value_fields)[:BATCH]
            )
            if not rows:
                break
            last_pk = rows[-1][pk_attname]
            if ensure_item_fk:
                item_ids = {row[ensure_item_fk] for row in rows}
                missing = self._missing_eve_type_ids(item_ids, local)
                if missing:
                    self._fetch_missing_eve_types(missing)
            if ensure_location_fk and source:
                loc_ids = {row[ensure_location_fk] for row in rows}
                for lid in sorted(loc_ids):
                    if (
                        not EveLocation.all_objects.using(local)
                        .filter(pk=lid)
                        .exists()
                    ):
                        self._ensure_location(lid, source, local)
            objs = [
                model(**{name: row[name] for name in create_fields})
                for row in rows
            ]
            model.objects.using(local).bulk_create(objs)
            created += len(rows)
            self.stdout.write(f"  {label} {created}…")
        self.stdout.write(f"  {label} imported: {created}")
        return created

    def _import_contracts(self, source, local, contract_ids):
        self._bulk_copy(
            model=EveMarketContract,
            source_qs=EveMarketContract.objects.using(source).filter(
                pk__in=contract_ids
            ),
            local=local,
            label="contracts",
            include_pk=True,
        )
        self._bulk_copy(
            model=EveMarketContractItem,
            source_qs=EveMarketContractItem.objects.using(source).filter(
                contract_id__in=contract_ids
            ),
            local=local,
            label="contract items",
            include_pk=False,
        )

    def _import_orders(self, source, local):
        self._bulk_copy(
            model=EveMarketItemOrder,
            source_qs=EveMarketItemOrder.objects.using(source).all(),
            local=local,
            label="orders",
            include_pk=False,
        )

    def _import_inferred_sales(self, source, local):
        self._bulk_copy(
            model=EveMarketInferredSale,
            source_qs=EveMarketInferredSale.objects.using(source).all(),
            local=local,
            label="inferred sales",
            include_pk=False,
            ensure_item_fk="item_id",
            ensure_location_fk="location_id",
            source=source,
        )

    def _import_order_book_sync(self, source, local):
        self.stdout.write("Importing order book syncs…")
        created = 0
        for row in EveMarketOrderBookSync.objects.using(source).iterator():
            EveMarketOrderBookSync.objects.using(local).update_or_create(
                location_id=row.location_id,
                defaults={"last_synced_at": row.last_synced_at},
            )
            created += 1
        self.stdout.write(f"  order book syncs upserted: {created}")

    def _import_location_prices(self, source, local):
        self._bulk_copy(
            model=EveMarketItemLocationPrice,
            source_qs=EveMarketItemLocationPrice.objects.using(source).all(),
            local=local,
            label="location prices",
            include_pk=False,
        )

    def _import_history(self, source, local, history_days, type_ids):
        cutoff = (timezone.now() - timedelta(days=history_days)).date()
        type_id_list = sorted(type_ids)
        self.stdout.write(
            f"Importing item history since {cutoff} "
            f"for {len(type_id_list)} type(s)…"
        )
        deleted, _ = (
            EveMarketItemHistory.objects.using(local)
            .filter(date__gte=cutoff, item_id__in=type_id_list)
            .delete()
        )
        self.stdout.write(
            self.style.WARNING(
                f"  cleared local history in window ({deleted})."
            )
        )
        # Chunk type ids — large IN lists against prod history cause
        # MySQL "Malformed packet" over the readonly connection.
        type_chunk = 150
        total = 0
        for i in range(0, len(type_id_list), type_chunk):
            chunk = type_id_list[i : i + type_chunk]
            total += self._bulk_copy(
                model=EveMarketItemHistory,
                source_qs=EveMarketItemHistory.objects.using(source).filter(
                    date__gte=cutoff, item_id__in=chunk
                ),
                local=local,
                label=f"history types {i + 1}-{i + len(chunk)}",
                include_pk=False,
            )
        self.stdout.write(f"  history imported total: {total}")

    def _write_local_totals(self, local):
        self.stdout.write(
            "Local totals: "
            f"contracts={EveMarketContract.objects.using(local).count()}, "
            f"contract_items={EveMarketContractItem.objects.using(local).count()}, "
            f"orders={EveMarketItemOrder.objects.using(local).count()}, "
            f"inferred={EveMarketInferredSale.objects.using(local).count()}, "
            f"syncs={EveMarketOrderBookSync.objects.using(local).count()}, "
            f"loc_prices={EveMarketItemLocationPrice.objects.using(local).count()}, "
            f"history={EveMarketItemHistory.objects.using(local).count()}."
        )
