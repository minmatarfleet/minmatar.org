"""
Copy buyback settings and accepted items from production_readonly into the
local default database, optionally re-seed the allowlist from local industry
data, and import recent EveMarketItemHistory for appraisal types.

Usage (from backend/, with DB_READONLY_* / production_readonly configured):

    pipenv run python manage.py import_buyback_from_production --clear --reseed

Options:
    --clear           Wipe local BuybackAcceptedItem before copying from prod.
    --reseed          After import, run seed_buyback_accepted_items on local data.
    --history-days N  Import Forge/baseline history for accepted (+ mineral) types
                      (default 14). Use 0 to skip.
    --dry-run         Validate and report counts without writing.
    --source          Database alias to read from (default: production_readonly).
"""

from __future__ import annotations

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from eveuniverse.models import EveType

from buyback.models import BuybackAcceptedItem, EveBuybackSettings
from eveonline.helpers.production_import import (
    assert_local_has_eve_types,
    validate_source_alias,
)
from eveonline.models import EveLocation
from industry.helpers.compressed_ore import ore_materials_per_portion
from market.helpers.pricing import JITA_REGION_ID
from market.models import EveMarketItemHistory

LOCATION_SKIP_COPY = frozenset(
    {"location_id", "deleted", "deleted_by_cascade"}
)
HISTORY_BATCH_TYPES = 150
HISTORY_BATCH_ROWS = 5000

SETTINGS_COPY_FIELDS = (
    "assignee_name",
    "accepted_categories",
    "demand_jita_buy",
    "surplus_jita_buy",
    "ore_refine",
    "rate_rules",
    "exclusions",
    "discord_thread_url",
    "leading_text",
    "active",
)


class Command(BaseCommand):
    help = (
        "Import buyback settings, accepted items, and appraisal history "
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
            help="Remove local BuybackAcceptedItem rows before copying from prod.",
        )
        parser.add_argument(
            "--reseed",
            action="store_true",
            help=(
                "After import, run seed_buyback_accepted_items against local "
                "orders/products (local seed policy)."
            ),
        )
        parser.add_argument(
            "--history-days",
            type=int,
            default=14,
            help=(
                "Import EveMarketItemHistory for accepted (+ ore mineral) types "
                "with date >= now - N days (default 14). Use 0 to skip."
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

        prod_settings = (
            EveBuybackSettings.objects.using(source).filter(pk=1).first()
        )
        if prod_settings is None:
            raise CommandError(f"No EveBuybackSettings on source={source}.")

        accepted = list(
            BuybackAcceptedItem.objects.using(source)
            .select_related("eve_type")
            .order_by("pk")
        )
        type_ids = {row.eve_type_id for row in accepted}
        assert_local_has_eve_types(type_ids, local)

        self.stdout.write(
            f"Source={source}: settings active={prod_settings.active}, "
            f"location_id={prod_settings.location_id}, "
            f"{len(accepted)} accepted items "
            f"({sum(1 for r in accepted if r.active)} active)."
        )

        if options["dry_run"]:
            if options["history_days"] > 0:
                history_types = self._history_type_ids(accepted, local)
                self.stdout.write(
                    f"Would import history for {len(history_types)} type(s) "
                    f"over {options['history_days']} day(s)."
                )
            if options["reseed"]:
                self.stdout.write(
                    "Would reseed buyback accepted items locally."
                )
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        self._import_settings_and_items(
            prod_settings,
            accepted,
            source,
            local,
            clear=options["clear"],
        )

        if options["reseed"]:
            self.stdout.write(
                "Reseeding buyback accepted items from local data…"
            )
            call_command("seed_buyback_accepted_items", stdout=self.stdout)

        if options["history_days"] > 0:
            # Re-read local accepted after optional reseed.
            local_accepted = list(
                BuybackAcceptedItem.objects.using(local)
                .filter(active=True)
                .select_related("eve_type")
            )
            history_types = self._history_type_ids(local_accepted, local)
            self._import_history(
                source,
                local,
                options["history_days"],
                history_types,
            )

        local_settings = EveBuybackSettings.objects.using(local).get(pk=1)
        active_count = (
            BuybackAcceptedItem.objects.using(local)
            .filter(active=True)
            .count()
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Buyback import done: active={local_settings.active}, "
                f"location_id={local_settings.location_id}, "
                f"accepted_active={active_count}."
            )
        )

    def _import_settings_and_items(
        self, prod_settings, accepted, source, local, *, clear
    ):
        with transaction.atomic(using=local):
            if prod_settings.location_id:
                self._ensure_location(prod_settings.location_id, source, local)

            local_settings, _ = EveBuybackSettings.objects.using(
                local
            ).get_or_create(pk=1)
            for field in SETTINGS_COPY_FIELDS:
                setattr(local_settings, field, getattr(prod_settings, field))
            local_settings.location_id = prod_settings.location_id
            local_settings.save(using=local)
            self.stdout.write("  Copied EveBuybackSettings.")

            if clear:
                deleted, _ = (
                    BuybackAcceptedItem.objects.using(local).all().delete()
                )
                self.stdout.write(
                    self.style.WARNING(
                        f"Cleared local BuybackAcceptedItem ({deleted} rows)."
                    )
                )

            created = 0
            updated = 0
            for row in accepted:
                _, was_created = BuybackAcceptedItem.objects.using(
                    local
                ).update_or_create(
                    eve_type_id=row.eve_type_id,
                    defaults={
                        "active": row.active,
                        "category": row.category,
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
            self.stdout.write(
                f"  Accepted items: created={created} updated={updated}."
            )

    def _history_type_ids(self, accepted_rows, local) -> set[int]:
        type_ids: set[int] = set()
        mineral_names: set[str] = set()
        for row in accepted_rows:
            if not row.active:
                continue
            type_ids.add(row.eve_type_id)
            if row.category == BuybackAcceptedItem.Category.ORE:
                try:
                    materials = ore_materials_per_portion(row.eve_type.name)
                except Exception:
                    continue
                mineral_names.update(materials.keys())
        if mineral_names:
            type_ids.update(
                EveType.objects.using(local)
                .filter(name__in=mineral_names)
                .values_list("id", flat=True)
            )
        return type_ids

    def _baseline_region_id(self, local) -> int:
        baseline = (
            EveLocation.objects.using(local)
            .filter(price_baseline=True)
            .first()
        )
        if baseline and baseline.region_id:
            return int(baseline.region_id)
        return JITA_REGION_ID

    def _import_history(self, source, local, history_days, type_ids):
        if not type_ids:
            self.stdout.write("No types for history import; skipping.")
            return
        cutoff = (timezone.now() - timedelta(days=history_days)).date()
        region_id = self._baseline_region_id(local)
        type_id_list = sorted(type_ids)
        self.stdout.write(
            f"Importing item history since {cutoff} region={region_id} "
            f"for {len(type_id_list)} type(s)…"
        )
        deleted, _ = (
            EveMarketItemHistory.objects.using(local)
            .filter(
                date__gte=cutoff,
                region_id=region_id,
                item_id__in=type_id_list,
            )
            .delete()
        )
        self.stdout.write(
            self.style.WARNING(
                f"  cleared local history in window ({deleted})."
            )
        )
        total = 0
        for i in range(0, len(type_id_list), HISTORY_BATCH_TYPES):
            chunk = type_id_list[i : i + HISTORY_BATCH_TYPES]
            qs = (
                EveMarketItemHistory.objects.using(source)
                .filter(
                    date__gte=cutoff,
                    region_id=region_id,
                    item_id__in=chunk,
                )
                .order_by("pk")
            )
            last_pk = 0
            while True:
                filter_kwargs = {"pk__gt": last_pk} if last_pk else {}
                rows = list(
                    qs.filter(**filter_kwargs).values(
                        "pk",
                        "region_id",
                        "item_id",
                        "date",
                        "average",
                        "highest",
                        "lowest",
                        "order_count",
                        "volume",
                    )[:HISTORY_BATCH_ROWS]
                )
                if not rows:
                    break
                last_pk = rows[-1]["pk"]
                EveMarketItemHistory.objects.using(local).bulk_create(
                    [
                        EveMarketItemHistory(
                            region_id=row["region_id"],
                            item_id=row["item_id"],
                            date=row["date"],
                            average=row["average"],
                            highest=row["highest"],
                            lowest=row["lowest"],
                            order_count=row["order_count"],
                            volume=row["volume"],
                        )
                        for row in rows
                    ]
                )
                total += len(rows)
                self.stdout.write(f"  history {total}…")
        self.stdout.write(f"  history imported total: {total}")

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
                f"  Restored EveLocation {location_id} ({loc.location_name})."
            )
            return
        obj = EveLocation(location_id=location_id, **fields)
        try:
            obj.save(using=local)
        except ValidationError:
            obj.price_baseline = False
            obj.save(using=local)
        self.stdout.write(
            f"  Copied EveLocation {location_id} ({loc.location_name})."
        )
