"""
Copy industry orders (and related lines / assignments) from production_readonly
into the default database.

Reads production via the read-only alias; writes only to default. Ensures
referenced EveLocation rows exist locally (copied from prod). Maps EveCharacter
by EVE character_id (creating minimal local rows if missing). Eve type IDs are
the same in eveuniverse locally as in production.

Usage (from backend/, with DB_READONLY_* / production_readonly configured):

    pipenv run python manage.py import_industry_orders_from_production --clear

Options:
    --clear     Delete all local industry orders (cascades to items/assignments)
                before import. Recommended if you already have orders locally.
    --dry-run   Validate and report counts without writing to default.
    --source    Database alias to read from (default: production_readonly).
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Prefetch
from eveuniverse.models import EveType

from eveonline.models import EveCharacter, EveLocation
from industry.models import (
    IndustryOrder,
    IndustryOrderItem,
    IndustryOrderItemAssignment,
)
from tribes.models import TribeGroup


class Command(BaseCommand):
    help = (
        "Import industry orders from production_readonly (or another alias) "
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
            help="Remove all IndustryOrder rows on default (cascades) before import.",
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

        orders = self._load_orders_from_source(source)
        char_pks, loc_ids, eve_type_ids = self._gather_ids_from_orders(orders)
        self._assert_local_has_eve_types(eve_type_ids, local)
        prod_chars_by_pk = self._fetch_prod_characters(char_pks, source)
        self._assert_all_characters_found(char_pks, prod_chars_by_pk)

        self._write_plan_summary(orders, loc_ids, source)

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        self._import_all(
            orders,
            source,
            local,
            clear=options["clear"],
            loc_ids=loc_ids,
            char_pks=char_pks,
            prod_chars_by_pk=prod_chars_by_pk,
        )
        self.stdout.write(
            self.style.SUCCESS(f"Imported {len(orders)} orders into {local}.")
        )

    def _validate_aliases(self, source, local):
        if source not in settings.DATABASES:
            raise CommandError(
                f'Database alias "{source}" is not configured. '
                "Set production_readonly (see app settings / DB_READONLY_*)."
            )
        if source == local:
            raise CommandError("Source and destination must differ.")

    def _load_orders_from_source(self, source):
        item_qs = (
            IndustryOrderItem.objects.using(source)
            .select_related("eve_type")
            .prefetch_related(
                Prefetch(
                    "assignments",
                    IndustryOrderItemAssignment.objects.using(
                        source
                    ).select_related("character"),
                )
            )
        )
        return list(
            IndustryOrder.objects.using(source)
            .select_related("character", "location")
            .prefetch_related(
                Prefetch("items", queryset=item_qs),
                "tribe_groups",
            )
            .order_by("pk")
        )

    def _gather_ids_from_orders(self, orders):
        char_pks = set()
        loc_ids = set()
        eve_type_ids = set()
        for order in orders:
            char_pks.add(order.character_id)
            if order.location_id:
                loc_ids.add(order.location_id)
            for item in order.items.all():
                eve_type_ids.add(item.eve_type_id)
                for asn in item.assignments.all():
                    char_pks.add(asn.character_id)
        return char_pks, loc_ids, eve_type_ids

    def _assert_local_has_eve_types(self, eve_type_ids, local):
        missing_types = sorted(
            tid
            for tid in eve_type_ids
            if not EveType.objects.using(local).filter(pk=tid).exists()
        )
        if missing_types:
            raise CommandError(
                "Local default DB is missing EveType rows for EVE type IDs: "
                f"{missing_types[:20]}{'…' if len(missing_types) > 20 else ''}. "
                "Load eveuniverse data locally first."
            )

    def _fetch_prod_characters(self, char_pks, source):
        return {
            c.pk: c
            for c in EveCharacter.objects.using(source).filter(pk__in=char_pks)
        }

    def _assert_all_characters_found(self, char_pks, prod_chars_by_pk):
        if len(prod_chars_by_pk) != len(char_pks):
            found = set(prod_chars_by_pk.keys())
            raise CommandError(
                f"Expected {len(char_pks)} EveCharacter rows from production, "
                f"found {len(found)}. Missing PKs: {sorted(char_pks - found)[:20]}"
            )

    def _write_plan_summary(self, orders, loc_ids, source):
        n_items = sum(len(list(o.items.all())) for o in orders)
        n_asn = sum(
            len(list(i.assignments.all()))
            for o in orders
            for i in o.items.all()
        )
        self.stdout.write(
            f"Source={source}: {len(orders)} orders, {n_items} items, "
            f"{n_asn} assignments, {len(loc_ids)} distinct locations."
        )

    def _import_all(
        self,
        orders,
        source,
        local,
        *,
        clear,
        loc_ids,
        char_pks,
        prod_chars_by_pk,
    ):
        with transaction.atomic(using=local):
            if clear:
                deleted, _ = IndustryOrder.objects.using(local).all().delete()
                self.stdout.write(
                    self.style.WARNING(
                        f"Cleared local industry orders ({deleted} rows)."
                    )
                )

            for lid in sorted(loc_ids):
                self._ensure_location(lid, source, local)

            prod_char_pk_to_local_pk = {
                pk: self._ensure_character(prod_chars_by_pk[pk], local)
                for pk in char_pks
            }

            for order in orders:
                self._copy_one_order(order, local, prod_char_pk_to_local_pk)

    def _copy_one_order(self, order, local, prod_char_pk_to_local_pk):
        new_order = IndustryOrder(
            needed_by=order.needed_by,
            fulfilled_at=order.fulfilled_at,
            public_short_code=order.public_short_code,
            contract_to=order.contract_to,
            character_id=prod_char_pk_to_local_pk[order.character_id],
            location_id=order.location_id,
        )
        new_order.save(using=local)
        IndustryOrder.objects.using(local).filter(pk=new_order.pk).update(
            created_at=order.created_at
        )

        src_tg_ids = list(order.tribe_groups.values_list("pk", flat=True))
        if src_tg_ids:
            existing_ids = (
                TribeGroup.objects.using(local)
                .filter(pk__in=src_tg_ids)
                .values_list("pk", flat=True)
            )
            new_order.tribe_groups.add(*existing_ids)

        for item in order.items.all():
            new_item = IndustryOrderItem.objects.using(local).create(
                order=new_order,
                eve_type_id=item.eve_type_id,
                quantity=item.quantity,
                self_assign_maximum=item.self_assign_maximum,
                target_unit_price=item.target_unit_price,
                target_estimated_margin=item.target_estimated_margin,
            )
            for asn in item.assignments.all():
                IndustryOrderItemAssignment.objects.using(local).create(
                    order_item=new_item,
                    character_id=prod_char_pk_to_local_pk[asn.character_id],
                    quantity=asn.quantity,
                    target_unit_price=asn.target_unit_price,
                    target_estimated_margin=asn.target_estimated_margin,
                    delivered_at=asn.delivered_at,
                )

    def _ensure_location(self, location_id, source, local):
        skip_copy = {"location_id", "deleted", "deleted_by_cascade"}
        existing = (
            EveLocation.all_objects.using(local).filter(pk=location_id).first()
        )
        if existing and not existing.deleted:
            return
        loc = EveLocation.objects.using(source).get(pk=location_id)
        fields = {
            field.name: getattr(loc, field.name)
            for field in EveLocation._meta.concrete_fields  # pylint: disable=protected-access
            if field.name not in skip_copy
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

    def _ensure_character(self, prod_char, local):
        """
        Map production EveCharacter.pk to local EveCharacter.pk via EVE character_id.
        """
        existing = (
            EveCharacter.objects.using(local)
            .filter(character_id=prod_char.character_id)
            .first()
        )
        if existing:
            return existing.pk
        return (
            EveCharacter.objects.using(local)
            .create(
                character_id=prod_char.character_id,
                character_name=prod_char.character_name or "",
                corporation_id=prod_char.corporation_id,
                alliance_id=prod_char.alliance_id,
                faction_id=prod_char.faction_id,
                token_id=None,
                user_id=None,
            )
            .pk
        )
