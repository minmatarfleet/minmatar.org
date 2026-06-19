from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from feed.models import FeedEvent, FeedKillmail, FeedMonitoredSystem


class Command(BaseCommand):
    help = "Audit feed scope: all FeedKillmail rows must be in monitored allowlist"

    def add_arguments(self, parser):
        parser.add_argument("--sample-hours", type=int, default=24)

    def handle(self, *args, **options):
        allowlist = set(
            FeedMonitoredSystem.objects.filter(is_active=True).values_list(
                "solar_system_id", flat=True
            )
        )
        since = timezone.now() - timedelta(hours=options["sample_hours"])
        killmails = FeedKillmail.objects.filter(killmail_time__gte=since)
        total = killmails.count()
        out_of_scope = killmails.exclude(solar_system_id__in=allowlist).count()

        bad_events = 0
        for event in FeedEvent.objects.filter(occurred_at__gte=since):
            system_id = (event.payload or {}).get("system_id")
            if system_id and system_id not in allowlist:
                bad_events += 1

        self.stdout.write(f"FeedKillmail in window: {total}")
        self.stdout.write(f"Out of allowlist: {out_of_scope}")
        self.stdout.write(f"FeedEvents with bad system_id: {bad_events}")

        if out_of_scope or bad_events:
            self.stderr.write(self.style.ERROR("Scope audit FAILED"))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS("Scope audit passed"))
