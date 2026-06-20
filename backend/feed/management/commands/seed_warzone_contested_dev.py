"""
Seed fake contested snapshot history for local Pulse warzone development.

Creates an hourly snapshot trail over the last 24 hours with varied contested %
deltas, then a current reading aligned with live ESI where available.

Usage (from backend/):

    pipenv run python manage.py seed_warzone_contested_dev
    pipenv run python manage.py seed_warzone_contested_dev --clear
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from feed.constants import FACTION_AMARR, FACTION_MINMATAR
from feed.helpers.fw_contested import fetch_fw_contested_from_esi
from feed.models import FeedMonitoredSystem, FeedSystemContestedSnapshot

# Stable per-system fake contested % at the start of the 24h window.
_FAKE_BASELINE: dict[str, float] = {
    "Huola": 64.0,
    "Kourmonen": 55.0,
    "Vard": 78.0,
    "Ardar": 42.0,
    "Ebolfer": 38.0,
    "Amamake": 12.0,
    "Lamaa": 71.0,
    "Siseide": 48.0,
    "Kamela": 33.0,
    "Tannolen": 61.0,
}

# Target delta from baseline to now (positive = heating up).
_FAKE_DELTA: dict[str, float] = {
    "Huola": 14.5,
    "Kourmonen": 18.2,
    "Vard": -6.0,
    "Ardar": 17.0,
    "Ebolfer": 20.8,
    "Amamake": 0.2,
    "Lamaa": -9.5,
    "Siseide": 11.0,
    "Kamela": 4.5,
    "Tannolen": -3.0,
}


def _baseline_percent(system_name: str, system_id: int) -> float:
    if system_name in _FAKE_BASELINE:
        return _FAKE_BASELINE[system_name]
    seed = system_id % 97
    return float(15 + (seed * 3) % 70)


def _delta_for_system(system_name: str, system_id: int) -> float:
    if system_name in _FAKE_DELTA:
        return _FAKE_DELTA[system_name]
    seed = system_id % 11
    return round((seed - 5) * 2.5, 1)


def _occupier_for_percent(
    contested_percent: float, *, amarr_front: bool
) -> int:
    if 0 < contested_percent < 100:
        return FACTION_MINMATAR if amarr_front else FACTION_AMARR
    if contested_percent >= 100:
        return FACTION_AMARR if amarr_front else FACTION_MINMATAR
    return FACTION_MINMATAR


class Command(BaseCommand):
    help = "Seed fake 24h contested snapshot history for local warzone UI development."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all local FeedSystemContestedSnapshot rows before seeding.",
        )
        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="How many hours of hourly snapshots to create (default: 24).",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            deleted, _ = FeedSystemContestedSnapshot.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f"Cleared {deleted} contested snapshots.")
            )

        monitored = list(
            FeedMonitoredSystem.objects.filter(is_active=True).order_by("name")
        )
        if not monitored:
            self.stderr.write(
                "No monitored systems — run seed_feed_monitored_systems first."
            )
            return

        try:
            esi_rows = fetch_fw_contested_from_esi()
        except Exception as exc:
            self.stderr.write(
                f"ESI fetch failed ({exc}); using fake values only."
            )
            esi_rows = {}

        now = timezone.now().replace(minute=50, second=0, microsecond=0)
        hours = max(2, options["hours"])
        snapshots: list[FeedSystemContestedSnapshot] = []

        for index, system in enumerate(monitored):
            baseline = _baseline_percent(system.name, system.solar_system_id)
            delta = _delta_for_system(system.name, system.solar_system_id)
            current = max(0.0, min(100.0, round(baseline + delta, 1)))

            esi_row = esi_rows.get(system.solar_system_id)
            amarr_front = index % 2 == 0
            occupier = (
                esi_row.occupier_faction_id
                if esi_row and esi_row.occupier_faction_id
                else _occupier_for_percent(current, amarr_front=amarr_front)
            )
            owner = (
                esi_row.victor_faction_id
                if esi_row and esi_row.victor_faction_id
                else FACTION_AMARR
            )

            for hour in range(hours, -1, -1):
                captured_at = now - timedelta(hours=hour)
                if hour == hours:
                    contested_percent = baseline
                elif hour == 0:
                    contested_percent = current
                else:
                    progress = (hours - hour) / hours
                    contested_percent = round(
                        baseline + (current - baseline) * progress,
                        1,
                    )
                    contested_percent = max(0.0, min(100.0, contested_percent))

                snapshots.append(
                    FeedSystemContestedSnapshot(
                        solar_system_id=system.solar_system_id,
                        contested_percent=contested_percent,
                        occupier_faction_id=occupier,
                        victor_faction_id=owner,
                        captured_at=captured_at,
                    )
                )

        FeedSystemContestedSnapshot.objects.bulk_create(
            snapshots, batch_size=500
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(snapshots)} snapshots for {len(monitored)} systems "
                f"({hours}h history ending {now.isoformat()})."
            )
        )
