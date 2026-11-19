"""Spread every in-scope character's sections across their intervals.

Run once before setting CHARACTER_SYNC_MODE=scheduled, so the first days
aren't one spike: in fanout mode every section was stamped inside the same
4-hour window. Existing rows keep their history; only next_due_at moves.

Usage:
  python manage.py spread_character_sync --dry-run
  python manage.py spread_character_sync
"""

import random

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from eveonline import character_sync as sync
from eveonline.models import EveCharacter, EveCharacterSyncState


class Command(BaseCommand):
    help = "Spread character sync due times evenly across each interval."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        now = timezone.now()
        audiences = sync.load_audiences()
        characters = dict(
            EveCharacter.objects.filter(
                pk__in=audiences.eligible(), esi_suspended=False
            ).values_list("pk", "character_id")
        )
        scopes = sync.token_scope_sets(characters.values())
        existing = {
            (row.character_id, row.section): row
            for row in EveCharacterSyncState.objects.filter(
                character_id__in=characters.keys()
            )
        }
        to_create, to_update = [], []
        for pk, character_id in characters.items():
            for section in sync.SECTIONS:
                if not audiences.in_scope(section.name, pk):
                    continue
                if not sync.granted(scopes.get(character_id, []), section):
                    continue
                interval = audiences.interval(section, pk)
                due = now + interval * random.random()
                row = existing.get((pk, section.name))
                if row is None:
                    to_create.append(
                        EveCharacterSyncState(
                            character_id=pk,
                            section=section.name,
                            next_due_at=due,
                        )
                    )
                else:
                    row.next_due_at = due
                    row.queued_at = None
                    to_update.append(row)
        self.stdout.write(
            f"{len(characters)} characters: {len(to_create)} rows to create, "
            f"{len(to_update)} to respread"
        )
        if options["dry_run"]:
            return
        with transaction.atomic():
            EveCharacterSyncState.objects.bulk_create(
                to_create, batch_size=1000, ignore_conflicts=True
            )
            EveCharacterSyncState.objects.bulk_update(
                to_update, ["next_due_at", "queued_at"], batch_size=1000
            )
        self.stdout.write("Done.")
