"""Create a local Unaligned NPSI fleet as if Post to schedule was clicked in Discord."""

from django.core.management.base import BaseCommand, CommandError

from fleets.helpers.npsi_local import (
    bootstrap_local_unaligned_post,
    local_fleet_schedule_url,
)


class Command(BaseCommand):
    help = (
        "Set up Unaligned NPSI locally, upsert a calendar event, and post it "
        "to the fleet schedule (same path as the Discord Post to schedule button)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="Unaligned",
            help="NpsiEventSource.name (default Unaligned)",
        )
        parser.add_argument(
            "--from-feed",
            action="store_true",
            help="Use the next upcoming event from the live Unaligned feed",
        )
        parser.add_argument(
            "--summary",
            default="Roaming Navies",
            help="Sample event title when not using --from-feed",
        )
        parser.add_argument(
            "--days-ahead",
            type=int,
            default=7,
            help="Sample event start offset in days (default 7)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Replace an already-posted event/fleet and post again",
        )

    def handle(self, *args, **options):
        try:
            event, fleet = bootstrap_local_unaligned_post(
                source_name=options["source"],
                from_feed=options["from_feed"],
                summary=options["summary"],
                days_ahead=options["days_ahead"],
                force=options["force"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        if options["from_feed"]:
            self.stdout.write(f"Using feed event: {event.summary}")
        else:
            self.stdout.write(f"Using sample event: {options['summary']}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Posted NPSI fleet #{fleet.id} ({fleet.type}) "
                f"at {fleet.formup_location.location_name if fleet.formup_location else 'unknown'}"
            )
        )
        self.stdout.write(f"Schedule: {local_fleet_schedule_url(fleet.id)}")
        self.stdout.write(
            f"NpsiExternalEvent #{event.id} status={event.status}"
        )
