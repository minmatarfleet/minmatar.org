"""
Copy EveSkillset rows from production_readonly into the local default database.

Reads production via the read-only alias; writes only to default. Upserts by
primary key so local FKs stay aligned with production IDs.

Usage (from backend/, with DB_READONLY_* / production_readonly configured):

    pipenv run python manage.py sync_skillsets_from_production
    pipenv run python manage.py sync_skillsets_from_production --clear
    pipenv run python manage.py sync_skillsets_from_production --dry-run

Options:
    --clear     Delete all local EveSkillset rows before import.
    --dry-run   Validate and report planned work without writing to default.
    --source    Database alias to read from (default: production_readonly).
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from eveonline.helpers.characters import create_eve_character_skillset
from eveonline.helpers.production_import import validate_source_alias
from eveonline.models import EveCharacterSkill, EveSkillset

SKILLSET_FIELDS = ("name", "skills", "total_skill_points")


class Command(BaseCommand):
    help = (
        "Sync EveSkillset rows from production_readonly "
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
            help="Remove all local EveSkillset rows before import.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not write; only validate and print planned work.",
        )

    def handle(self, *args, **options):
        source = options["source"]
        local = "default"
        validate_source_alias(source, local)

        prod_skillsets = list(EveSkillset.objects.using(source).order_by("pk"))
        self.stdout.write(f"Source={source}: {len(prod_skillsets)} skillsets.")
        for skillset in prod_skillsets:
            self.stdout.write(
                f"  [{skillset.pk}] {skillset.name} "
                f"({skillset.total_skill_points:,} SP)"
            )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        with transaction.atomic(using=local):
            if options["clear"]:
                deleted, _ = EveSkillset.objects.using(local).all().delete()
                self.stdout.write(
                    self.style.WARNING(
                        f"Cleared local skillsets ({deleted} rows)."
                    )
                )

            created = 0
            updated = 0
            for prod in prod_skillsets:
                defaults = {
                    field: getattr(prod, field) for field in SKILLSET_FIELDS
                }
                _, was_created = EveSkillset.objects.using(
                    local
                ).update_or_create(
                    pk=prod.pk,
                    defaults=defaults,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        local_count = EveSkillset.objects.using(local).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. created={created} updated={updated} "
                f"local_total={local_count}"
            )
        )

        rebuilt = self._rebuild_character_skillsets(local)
        if rebuilt:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Rebuilt EveCharacterSkillset for {rebuilt} characters."
                )
            )

    def _rebuild_character_skillsets(self, local: str) -> int:
        character_ids = list(
            EveCharacterSkill.objects.using(local)
            .values_list("character__character_id", flat=True)
            .distinct()
        )
        skillsets = list(EveSkillset.objects.using(local).all())
        if not character_ids or not skillsets:
            return 0

        for character_id in character_ids:
            for skillset in skillsets:
                create_eve_character_skillset(character_id, skillset)
        return len(character_ids)
