"""Send an NPSI Post-to-schedule DM (ops / local preview)."""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

import requests

from fleets.helpers.npsi_ingest import upsert_feed_item
from fleets.models import NpsiEventSource


class Command(BaseCommand):
    help = (
        "Poll an NPSI feed and DM a Discord user with a Post to schedule "
        "button. Staff can click the button."
    )

    def add_arguments(self, parser):
        parser.add_argument("--discord-user-id", type=int, required=True)
        parser.add_argument(
            "--source",
            default="Unaligned",
            help="NpsiEventSource.name (default Unaligned)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-send even if already notified",
        )
        parser.add_argument(
            "--include-past",
            action="store_true",
            help="Include past feed items (preview)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=1,
            help="Max events to DM (default 1)",
        )

    def handle(self, *args, **options):
        discord_user_id = options["discord_user_id"]
        source = NpsiEventSource.objects.filter(name=options["source"]).first()
        if source is None:
            raise CommandError(f"Unknown NPSI source {options['source']}")
        if source.default_audience_id is None:
            raise CommandError(
                "Source has no default audience. Set it in Django admin first."
            )

        response = requests.get(source.feed_url, timeout=15)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or not payload:
            raise CommandError("Feed returned no events")

        now = timezone.now()
        notified = 0
        for item in payload:
            if not isinstance(item, dict):
                continue
            if notified >= options["limit"]:
                break
            result = upsert_feed_item(
                source,
                item,
                now=now,
                force_renotify=options["force"],
                notify_discord_user_id=discord_user_id,
                include_past=options["include_past"],
            )
            notified += result["notified"]

        if notified == 0:
            raise CommandError(
                "No DMs sent. Upcoming events may already be notified; "
                "try --force and/or --include-past."
            )
        self.stdout.write(self.style.SUCCESS(f"Sent {notified} NPSI DM(s)"))
