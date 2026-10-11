"""
Copy EveCharacterMiningEntry rows (and related EveMarketPrice) from
production_readonly into the local default database for the last N days.

Ensures minimal EveCharacter rows exist for each ESI character_id in the
import window.

Usage (from backend/, with DB_READONLY_* / production_readonly configured):

    pipenv run python manage.py import_mining_entries_from_production
    pipenv run python manage.py import_mining_entries_from_production --days 30
    pipenv run python manage.py import_mining_entries_from_production --clear
    pipenv run python manage.py import_mining_entries_from_production --dry-run

Options:
    --days      Include ledger rows with date >= today - N days (default: 30).
    --clear     Delete local mining entries in the same window before import.
    --dry-run   Validate and report counts without writing to default.
    --source    Database alias to read from (default: production_readonly).
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from eveuniverse.models import EveMarketPrice

from eveonline.helpers.production_import import (
    ensure_character_from_prod,
    fetch_eve_types_from_esi,
    missing_eve_type_ids,
    validate_source_alias,
)
from eveonline.models import EveCharacter
from eveonline.models.characters import EveCharacterMiningEntry


class Command(BaseCommand):
    help = (
        "Import EveCharacterMiningEntry (and EveMarketPrice) from "
        "production_readonly into the local default database."
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
            default=30,
            help="Import mining ledger rows within this many days (default 30).",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete local mining entries in the import window first.",
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
        validate_source_alias(source, local)

        if days < 1:
            raise CommandError("--days must be >= 1.")

        cutoff = timezone.now().date() - timedelta(days=days)
        entries = list(
            EveCharacterMiningEntry.objects.using(source)
            .filter(date__gte=cutoff)
            .select_related("character")
            .order_by("date", "pk")
        )

        type_ids = {e.eve_type_id for e in entries if e.eve_type_id}
        esi_char_ids = {
            e.character.character_id for e in entries if e.character_id
        }
        missing_types = missing_eve_type_ids(type_ids, local)

        prod_prices = {
            p.eve_type_id: p
            for p in EveMarketPrice.objects.using(source).filter(
                eve_type_id__in=type_ids
            )
        }
        prod_chars = {
            c.character_id: c
            for c in EveCharacter.objects.using(source).filter(
                character_id__in=esi_char_ids
            )
        }

        self.stdout.write(
            f"Source={source}, date>={cutoff.isoformat()}: "
            f"{len(entries)} mining entries, {len(esi_char_ids)} characters, "
            f"{len(type_ids)} ore types ({len(missing_types)} missing locally), "
            f"{len(prod_prices)} market prices."
        )

        if options["dry_run"]:
            if options["clear"]:
                local_clear_count = (
                    EveCharacterMiningEntry.objects.using(local)
                    .filter(date__gte=cutoff)
                    .count()
                )
                self.stdout.write(
                    f"Would clear {local_clear_count} local mining entries "
                    f"in window."
                )
            if missing_types:
                self.stdout.write(
                    f"Would fetch {len(missing_types)} EveType(s) from ESI: "
                    f"{missing_types[:20]}"
                    f"{'…' if len(missing_types) > 20 else ''}."
                )
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        if missing_types:
            self.stdout.write(
                f"Fetching {len(missing_types)} missing EveType(s) from ESI…"
            )
            fetch_eve_types_from_esi(missing_types)
            still_missing = missing_eve_type_ids(type_ids, local)
            if still_missing:
                raise CommandError(
                    "Failed to load EveType rows for EVE type IDs: "
                    f"{still_missing[:20]}"
                    f"{'…' if len(still_missing) > 20 else ''}."
                )

        with transaction.atomic(using=local):
            if options["clear"]:
                deleted, _ = (
                    EveCharacterMiningEntry.objects.using(local)
                    .filter(date__gte=cutoff)
                    .delete()
                )
                self.stdout.write(f"  Cleared {deleted} local mining entries.")

            local_char_by_esi = {
                esi_id: ensure_character_from_prod(
                    esi_id, prod_chars.get(esi_id), local
                )
                for esi_id in sorted(esi_char_ids)
            }

            created = 0
            updated = 0
            for entry in entries:
                local_char = local_char_by_esi.get(
                    entry.character.character_id
                )
                if not local_char:
                    continue
                _, was_created = EveCharacterMiningEntry.objects.using(
                    local
                ).update_or_create(
                    character=local_char,
                    eve_type_id=entry.eve_type_id,
                    date=entry.date,
                    solar_system_id=entry.solar_system_id,
                    defaults={"quantity": entry.quantity},
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

            prices_upserted = 0
            for type_id, prod_price in prod_prices.items():
                EveMarketPrice.objects.using(local).update_or_create(
                    eve_type_id=type_id,
                    defaults={
                        "average_price": prod_price.average_price,
                        "adjusted_price": prod_price.adjusted_price,
                    },
                )
                prices_upserted += 1

        local_count = (
            EveCharacterMiningEntry.objects.using(local)
            .filter(date__gte=cutoff)
            .count()
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Synced mining entries into {local}: {created} created, "
                f"{updated} updated, {prices_upserted} market prices. "
                f"Local entries in window={local_count}."
            )
        )
