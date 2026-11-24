"""manage.py voice_status: leases, connected count, last heartbeat."""

import json

from django.core.management.base import BaseCommand

from voice import publisher, store
from voice.models import VoiceChannelLease, VoiceIdentity
from voice.tasks import heartbeat_problem


class Command(BaseCommand):
    help = "Show fleet voice state: leases, the voice service heartbeat."

    def add_arguments(self, parser):
        parser.add_argument(
            "--rebuild",
            action="store_true",
            help="Republish every voice record to Redis first.",
        )

    def handle(self, *args, **options):
        if options["rebuild"]:
            count = publisher.rebuild_all()
            self.stdout.write(f"Republished {count} records")
        self.stdout.write(f"Identities: {VoiceIdentity.objects.count()}")
        leases = VoiceChannelLease.active().order_by("branch")
        if not leases:
            self.stdout.write("Leases: none")
        for lease in leases:
            self.stdout.write(
                f"Fleet {lease.branch}: fleet {lease.fleet_id} since "
                f"{lease.started_at:%Y-%m-%d %H:%M}"
                + (
                    f", ends {lease.release_after:%H:%M}"
                    if lease.release_after
                    else ""
                )
            )
        raw = store.get_client().get(store.HEARTBEAT_KEY)
        problem = heartbeat_problem(raw)
        if raw is not None:
            beat = json.loads(raw)
            at, sessions = beat.get("at"), beat.get("sessions")
            self.stdout.write(f"Heartbeat: {at} sessions={sessions}")
        state = problem or "healthy"
        self.stdout.write(f"Voice service: {state}")
