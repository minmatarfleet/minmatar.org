from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from feed.helpers.ingest import upsert_feed_killmail_from_r2z2
from feed.helpers.monitored_systems import get_monitored_system_ids


class Command(BaseCommand):
    help = "Import a killmail from R2Z2-style JSON file or stdin"

    def add_arguments(self, parser):
        parser.add_argument("--file", dest="file_path", required=True)
        parser.add_argument(
            "--killmail-id", dest="killmail_id", type=int, default=None
        )

    def handle(self, *args, **options):
        path = Path(options["file_path"])
        payload = json.loads(path.read_text(encoding="utf-8"))
        if options["killmail_id"]:
            payload.setdefault("killmail_id", options["killmail_id"])
        allowlist = get_monitored_system_ids(force_refresh=True)
        result = upsert_feed_killmail_from_r2z2(payload, allowlist=allowlist)
        if result:
            self.stdout.write(
                self.style.SUCCESS(f"Imported killmail {result.killmail_id}")
            )
        else:
            self.stdout.write(
                self.style.WARNING("Killmail discarded (scope/NPC filter)")
            )
