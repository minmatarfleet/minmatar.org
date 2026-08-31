"""
Copy freight courier contracts (EveCorporationContract) from production_readonly
into the local default database for the last N days.

Also ensures EveLocation rows used by those contracts exist locally, and creates
minimal EveCharacter rows for issuer/acceptor display.

Usage (from backend/, with DB_READONLY_* / production_readonly configured):

    pipenv run python manage.py import_freight_contracts_from_production
    pipenv run python manage.py import_freight_contracts_from_production --days 30
    pipenv run python manage.py import_freight_contracts_from_production --dry-run

Options:
    --days      Include contracts issued or completed within this many days
                (default: 30).
    --dry-run   Validate and report counts without writing to default.
    --source    Database alias to read from (default: production_readonly).
"""

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from eveonline.helpers.production_import import ensure_character_from_prod
from eveonline.models import EveCharacter, EveCorporation, EveLocation
from freight.models import (
    FREIGHT_CORPORATION_ID,
    FreightContract,
)

LOCATION_SKIP_COPY = frozenset(
    {"location_id", "deleted", "deleted_by_cascade"}
)

CONTRACT_COPY_FIELDS = (
    "type",
    "status",
    "availability",
    "issuer_id",
    "issuer_corporation_id",
    "assignee_id",
    "acceptor_id",
    "for_corporation",
    "date_issued",
    "date_expired",
    "date_accepted",
    "date_completed",
    "days_to_complete",
    "price",
    "reward",
    "collateral",
    "buyout",
    "volume",
    "start_location_id",
    "end_location_id",
    "title",
)


class Command(BaseCommand):
    help = (
        "Import freight courier contracts from production_readonly "
        "into the local default database."
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
            help="Import contracts issued or completed within this many days.",
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
        contracts = list(
            FreightContract.objects.using(source)
            .filter(Q(date_issued__gte=cutoff) | Q(date_completed__gte=cutoff))
            .select_related("corporation")
            .order_by("-date_issued")
        )

        status_counts = {
            row["status"]: row["n"]
            for row in FreightContract.objects.using(source)
            .filter(Q(date_issued__gte=cutoff) | Q(date_completed__gte=cutoff))
            .values("status")
            .annotate(n=Count("contract_id"))
        }

        loc_ids = self._gather_location_ids(contracts)
        char_ids = self._gather_character_ids(contracts)
        prod_chars = {
            c.character_id: c
            for c in EveCharacter.objects.using(source).filter(
                character_id__in=char_ids
            )
        }
        missing_char_ids = sorted(char_ids - set(prod_chars))

        self.stdout.write(
            f"Source={source}, last {days} days (cutoff {cutoff.isoformat()}): "
            f"{len(contracts)} contracts {status_counts}."
        )
        self.stdout.write(
            f"Locations={len(loc_ids)}, characters={len(char_ids)} "
            f"({len(missing_char_ids)} missing from prod EveCharacter)."
        )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        local_corp = (
            EveCorporation.objects.using(local)
            .filter(corporation_id=FREIGHT_CORPORATION_ID)
            .first()
        )
        if not local_corp:
            prod_corp = (
                EveCorporation.objects.using(source)
                .filter(corporation_id=FREIGHT_CORPORATION_ID)
                .first()
            )
            if not prod_corp:
                raise CommandError(
                    f"Freight corporation {FREIGHT_CORPORATION_ID} missing "
                    f"in {source} and {local}."
                )
            local_corp = EveCorporation.objects.using(local).create(
                corporation_id=prod_corp.corporation_id,
                name=prod_corp.name,
                ticker=prod_corp.ticker,
            )
            self.stdout.write(
                f"  Copied EveCorporation {local_corp.corporation_id} "
                f"({local_corp.name})."
            )

        with transaction.atomic(using=local):
            for lid in sorted(loc_ids):
                self._ensure_location(lid, source, local)

            for character_id in sorted(char_ids):
                ensure_character_from_prod(
                    character_id,
                    prod_chars.get(character_id),
                    local,
                )

            created = 0
            updated = 0
            for prod_contract in contracts:
                was_created = self._upsert_contract(
                    prod_contract, local_corp, local
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        local_count = (
            FreightContract.objects.using(local)
            .filter(Q(date_issued__gte=cutoff) | Q(date_completed__gte=cutoff))
            .count()
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Synced into {local}: {created} created, {updated} updated. "
                f"Local freight contracts in window={local_count}."
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

    def _gather_location_ids(self, contracts):
        loc_ids = set()
        for contract in contracts:
            if contract.start_location_id:
                loc_ids.add(int(contract.start_location_id))
            if contract.end_location_id:
                loc_ids.add(int(contract.end_location_id))
        return loc_ids

    def _gather_character_ids(self, contracts):
        char_ids = set()
        for contract in contracts:
            if contract.issuer_id and contract.issuer_id > 0:
                char_ids.add(int(contract.issuer_id))
            if (
                contract.acceptor_id
                and contract.acceptor_id > 0
                and contract.acceptor_id != FREIGHT_CORPORATION_ID
            ):
                char_ids.add(int(contract.acceptor_id))
        return char_ids

    def _ensure_location(self, location_id, source, local):
        existing = (
            EveLocation.all_objects.using(local).filter(pk=location_id).first()
        )
        if existing and not existing.deleted:
            return

        loc = EveLocation.objects.using(source).filter(pk=location_id).first()
        if not loc:
            self.stdout.write(
                self.style.WARNING(
                    f"  Skip EveLocation {location_id} — not in {source}."
                )
            )
            return

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

    def _upsert_contract(self, prod_contract, local_corp, local):
        defaults = {
            field: getattr(prod_contract, field)
            for field in CONTRACT_COPY_FIELDS
        }
        defaults["corporation"] = local_corp

        existing = (
            FreightContract.objects.using(local)
            .filter(contract_id=prod_contract.contract_id)
            .first()
        )
        if existing:
            for key, value in defaults.items():
                setattr(existing, key, value)
            existing.save(using=local)
            return False

        FreightContract(
            contract_id=prod_contract.contract_id,
            **defaults,
        ).save(using=local)
        return True
