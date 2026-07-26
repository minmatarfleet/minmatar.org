from __future__ import annotations

from datetime import datetime, timezone

from django.core.management.base import BaseCommand

from feed.helpers.capital_pings import (
    build_capital_ping_payload,
    maybe_notify_capital_kill,
)


def sample_capital_kill_payload() -> dict:
    """Synthetic capital loss in Amamake for Discord smoke tests."""
    killmail_time = (
        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    attackers = [
        {
            "character_id": 2112000001 + index,
            "corporation_id": 98000001,
            "alliance_id": 99000001,
            "ship_type_id": 17726,
            "damage_done": 1500 - index,
            "final_blow": index == 0,
        }
        for index in range(12)
    ]
    attackers.extend(
        {
            "character_id": 2112000100 + index,
            "corporation_id": 98000002,
            "alliance_id": 99000001,
            "ship_type_id": 17726,
            "damage_done": 900 - index,
            "final_blow": False,
        }
        for index in range(8)
    )
    raw = {
        "killmail_id": int(datetime.now(timezone.utc).timestamp()),
        "killmail_time": killmail_time,
        "solar_system_id": 30002537,
        "victim": {
            "character_id": 2111000001,
            "corporation_id": 98000003,
            "ship_type_id": 73790,
            "damage_taken": 250000,
        },
        "attackers": attackers,
    }
    return {
        "killmail": raw,
        "hash": "capital_ping_smoke_test",
        "zkb": {"npc": False, "totalValue": 4_500_000_000},
        "sequence_id": 1,
    }


class Command(BaseCommand):
    help = "Send a sample capital-kill Discord ping (Amamake smoke test)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Build and print the payload without posting to Discord.",
        )

    def handle(self, *args, **options):
        payload = sample_capital_kill_payload()
        if options["dry_run"]:
            raw = payload["killmail"]
            built = build_capital_ping_payload(
                raw, zkb=payload["zkb"], distance_ly=0.0
            )
            self.stdout.write(self.style.SUCCESS(str(built)))
            return

        sent = maybe_notify_capital_kill(payload)
        if sent:
            self.stdout.write(
                self.style.SUCCESS(
                    "Capital ping posted to the configured Discord channel."
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    "Capital ping was not sent. Enable receive_capital_pings "
                    "on a Discord channel in admin, and check bot permissions."
                )
            )
