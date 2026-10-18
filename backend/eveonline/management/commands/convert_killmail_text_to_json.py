"""Rewrite EveCharacterKillmail attackers/items from Python repr to JSON.

Safe to run while the app is live and safe to re-run: readers accept both
formats, rows already in the target format are skipped, and rows that cannot
be parsed are left untouched and counted. ``--reverse`` writes the old repr
back, so the conversion can be undone.

    manage.py convert_killmail_text_to_json --dry-run
    manage.py convert_killmail_text_to_json --batch-size 500 --sleep 0.2
    manage.py convert_killmail_text_to_json --reverse
"""

import time

from django.core.management.base import BaseCommand
from django.db import transaction

from eveonline.helpers.killmail_text import (
    json_to_repr_text,
    load_killmail_list,
    repr_to_json_text,
)
from eveonline.models import EveCharacterKillmail

FIELDS = ("attackers", "items")


def convert_killmail_text(
    *,
    reverse: bool = False,
    batch_size: int = 500,
    dry_run: bool = False,
    limit: int | None = None,
    sleep_seconds: float = 0,
    using: str = "default",
) -> dict:
    """Walk the table by primary key in batches and rewrite each field.

    Keyset paging (``id > last``) keeps every query short instead of
    holding one cursor open across the whole table. Only ``attackers`` and
    ``items`` are written (``updated_at`` is left alone).
    """
    convert = json_to_repr_text if reverse else repr_to_json_text
    stats = {"scanned": 0, "updated": 0, "unchanged": 0, "unreadable": 0}
    last_id = None
    queryset = EveCharacterKillmail.objects.using(using).order_by("id")
    while limit is None or stats["scanned"] < limit:
        size = batch_size
        if limit is not None:
            size = min(size, limit - stats["scanned"])
        page = queryset
        if last_id is not None:
            page = page.filter(id__gt=last_id)
        rows = list(page.only("id", *FIELDS)[:size])
        if not rows:
            break
        last_id = rows[-1].id
        changed = []
        for row in rows:
            stats["scanned"] += 1
            dirty = False
            for field in FIELDS:
                value = getattr(row, field)
                new_value = convert(value)
                if new_value is not None:
                    setattr(row, field, new_value)
                    dirty = True
                elif load_killmail_list(value) is None:
                    stats["unreadable"] += 1
            if dirty:
                changed.append(row)
            else:
                stats["unchanged"] += 1
        stats["updated"] += len(changed)
        if changed and not dry_run:
            with transaction.atomic(using=using):
                EveCharacterKillmail.objects.using(using).bulk_update(
                    changed, list(FIELDS)
                )
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return stats


class Command(BaseCommand):
    help = (
        "Convert EveCharacterKillmail attackers/items text from Python "
        "repr to JSON (or back with --reverse)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--sleep", type=float, default=0.0)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--reverse", action="store_true")

    def handle(self, *args, **options):
        stats = convert_killmail_text(
            reverse=options["reverse"],
            batch_size=max(1, options["batch_size"]),
            dry_run=options["dry_run"],
            limit=options["limit"],
            sleep_seconds=options["sleep"],
        )
        prefix = "Would convert" if options["dry_run"] else "Converted"
        self.stdout.write(
            f"{prefix} {stats['updated']} of {stats['scanned']} killmails "
            f"({stats['unchanged']} unchanged, {stats['unreadable']} "
            "unreadable fields left as they were)."
        )
