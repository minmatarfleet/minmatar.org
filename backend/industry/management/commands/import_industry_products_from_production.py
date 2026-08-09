"""
Copy IndustryProduct rows (strategy, breakdown, supplied_for) from
production_readonly into the default database.

Reads production via the read-only alias; writes only to default. Upserts by
eve_type_id. Bypasses IndustryProduct.save() side effects (auto component
creation) so the local graph matches production, then restores supplied_for.

Usage (from backend/, with DB_READONLY_* / production_readonly configured):

    pipenv run python manage.py import_industry_products_from_production --clear

Options:
    --clear     Delete all local IndustryProduct rows before import.
    --dry-run   Validate and report counts without writing to default.
    --source    Database alias to read from (default: production_readonly).
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import models, transaction

from eveonline.helpers.production_import import (
    assert_local_has_eve_types,
    validate_source_alias,
)
from industry.helpers.type_breakdown import type_ids_in_breakdown
from industry.models import IndustryProduct


class Command(BaseCommand):
    help = (
        "Import IndustryProduct rows from production_readonly "
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
            help="Remove all IndustryProduct rows on default before import.",
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

        products = list(
            IndustryProduct.objects.using(source)
            .select_related("eve_type")
            .prefetch_related("supplied_for")
            .order_by("pk")
        )
        type_ids = self._gather_type_ids(products)
        assert_local_has_eve_types(
            type_ids,
            local,
            hint="Load eveuniverse data locally first (eveuniverse_load_types).",
        )

        strategies = {}
        for product in products:
            strategies[product.strategy] = (
                strategies.get(product.strategy, 0) + 1
            )
        self.stdout.write(
            f"Source={source}: {len(products)} IndustryProduct rows, "
            f"{len(type_ids)} distinct EveType IDs. "
            f"Strategies={strategies}."
        )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        self._import_all(products, local, clear=options["clear"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {len(products)} IndustryProduct rows into {local}."
            )
        )

    def _gather_type_ids(self, products) -> set[int]:
        type_ids: set[int] = set()
        for product in products:
            type_ids.add(product.eve_type_id)
            type_ids.update(type_ids_in_breakdown(product.breakdown))
            for parent in product.supplied_for.all():
                type_ids.add(parent.eve_type_id)
        return type_ids

    def _import_all(self, products, local, *, clear):
        with transaction.atomic(using=local):
            if clear:
                deleted, _ = (
                    IndustryProduct.objects.using(local).all().delete()
                )
                self.stdout.write(
                    self.style.WARNING(
                        f"Cleared local IndustryProduct ({deleted} rows)."
                    )
                )

            local_by_type: dict[int, IndustryProduct] = {}
            for product in products:
                local_product = self._upsert_product(product, local)
                local_by_type[product.eve_type_id] = local_product

            for product in products:
                local_product = local_by_type[product.eve_type_id]
                parent_type_ids = [
                    parent.eve_type_id for parent in product.supplied_for.all()
                ]
                parent_pks = [
                    local_by_type[tid].pk
                    for tid in parent_type_ids
                    if tid in local_by_type
                ]
                local_product.supplied_for.set(parent_pks)

    def _upsert_product(self, prod_product, local) -> IndustryProduct:
        """
        Upsert strategy/breakdown without IndustryProduct.save() side effects.
        """
        existing = (
            IndustryProduct.objects.using(local)
            .filter(eve_type_id=prod_product.eve_type_id)
            .first()
        )
        if existing:
            IndustryProduct.objects.using(local).filter(pk=existing.pk).update(
                strategy=prod_product.strategy,
                breakdown=prod_product.breakdown,
            )
            existing.strategy = prod_product.strategy
            existing.breakdown = prod_product.breakdown
            return existing

        obj = IndustryProduct(
            eve_type_id=prod_product.eve_type_id,
            strategy=prod_product.strategy,
            breakdown=prod_product.breakdown,
        )
        # Bypass IndustryProduct.save() (full_clean + supplied_for rebuild).
        models.Model.save(obj, using=local)
        return obj
