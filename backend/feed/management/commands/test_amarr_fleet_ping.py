from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from feed.helpers.amarr_fleet_pings import (
    build_amarr_fleet_alert_payload,
    maybe_notify_amarr_fleet,
)
from feed.models import FeedEvent


def sample_amarr_fleet_event() -> FeedEvent:
    """Synthetic Amarr fleet_active event for Discord smoke tests."""
    return FeedEvent(
        kind=FeedEvent.Kind.FLEET_ACTIVE,
        occurred_at=timezone.now(),
        title="Medium Amarr fleet active",
        subheader="Amamake · 12 kills · 15 pilots · ~10m",
        preview="Medium fleet involving battlecruisers and frigates.",
        body="",
        accent=FeedEvent.Accent.AMARR,
        payload={
            "faction": "amarr",
            "system_id": 30002537,
            "system_name": "Amamake",
            "kills": 12,
            "pilots": 15,
            "roster": [
                {"character_id": 2111000001, "name": "Amarr Pilot"},
            ],
            "roster_total": 15,
            "engagement_tier": "medium",
        },
        rollup_code="fleet_active",
        rollup_version=1,
        cluster_key=(
            f"fleet_active:30002537:500003:"
            f"{timezone.now().strftime('%Y-%m-%dT%H:%M')}"
        ),
        is_active=True,
    )


class Command(BaseCommand):
    help = "Send a sample Amarr-fleet Discord ping (smoke test)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Build and print the payload without posting to Discord.",
        )

    def handle(self, *args, **options):
        event = sample_amarr_fleet_event()
        if options["dry_run"]:
            built = build_amarr_fleet_alert_payload(
                system_name="Amamake",
                title=event.title,
                subheader=event.subheader,
                preview=event.preview,
                kills=12,
                pilots=15,
                roster=event.payload["roster"],
                roster_total=15,
            )
            self.stdout.write(self.style.SUCCESS(str(built)))
            return

        event.save()
        sent = maybe_notify_amarr_fleet(event)
        if sent:
            self.stdout.write(
                self.style.SUCCESS(
                    "Amarr fleet ping posted to the configured Discord channel."
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    "Amarr fleet ping was not sent. Enable "
                    "receive_amarr_fleet_pings on a Discord channel in admin, "
                    "and check bot permissions."
                )
            )
