from __future__ import annotations

import json
from pathlib import Path

import requests
from django.core.management.base import BaseCommand

from feed.constants import FW_WARZONE_REGIONS
from feed.helpers.monitored_systems import invalidate_monitored_systems_cache
from feed.models import FeedMonitoredSystem

FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent
    / "tests"
    / "fixtures"
    / "fw_monitored_systems.json"
)


def _load_fixture_systems() -> list[dict]:
    if FIXTURE_PATH.exists():
        return json.loads(FIXTURE_PATH.read_text())
    return [
        {"solar_system_id": 30002538, "name": "Vard"},
        {"solar_system_id": 30003067, "name": "Huola"},
        {"solar_system_id": 30003068, "name": "Kourmonen"},
        {"solar_system_id": 30004299, "name": "Sakht"},
        {"solar_system_id": 30002812, "name": "Tannolen"},
    ]


def seed_from_fixture() -> int:
    count = 0
    for row in _load_fixture_systems():
        _, created = FeedMonitoredSystem.objects.update_or_create(
            solar_system_id=row["solar_system_id"],
            defaults={
                "name": row["name"],
                "source": FeedMonitoredSystem.Source.FW_WARZONE,
                "is_active": True,
            },
        )
        if created:
            count += 1
    invalidate_monitored_systems_cache()
    return count


def _esi_headers() -> dict[str, str]:
    return {"User-Agent": "minmatar.org-feed-seed/1.0"}


def _region_id_for_constellation(
    constellation_id: int,
    *,
    cache: dict[int, int],
) -> int | None:
    if constellation_id in cache:
        return cache[constellation_id]
    response = requests.get(
        f"https://esi.evetech.net/latest/universe/constellations/{constellation_id}/",
        headers=_esi_headers(),
        timeout=30,
    )
    if response.status_code != 200:
        return None
    region_id = response.json().get("region_id")
    if region_id is not None:
        cache[constellation_id] = region_id
    return region_id


def seed_from_esi() -> int:
    fw_response = requests.get(
        "https://esi.evetech.net/latest/fw/systems/",
        headers=_esi_headers(),
        timeout=60,
    )
    fw_response.raise_for_status()
    fw_systems = fw_response.json()

    region_ids = set(FW_WARZONE_REGIONS.keys())
    constellation_regions: dict[int, int] = {}
    count = 0
    for entry in fw_systems:
        system_id = entry.get("solar_system_id")
        if not system_id:
            continue
        sys_response = requests.get(
            f"https://esi.evetech.net/latest/universe/systems/{system_id}/",
            headers=_esi_headers(),
            timeout=30,
        )
        if sys_response.status_code != 200:
            continue
        system_data = sys_response.json()
        constellation_id = system_data.get("constellation_id")
        if not constellation_id:
            continue
        region_id = _region_id_for_constellation(
            constellation_id, cache=constellation_regions
        )
        if region_id not in region_ids:
            continue
        _, created = FeedMonitoredSystem.objects.update_or_create(
            solar_system_id=system_id,
            defaults={
                "name": system_data.get("name", f"System {system_id}"),
                "source": FeedMonitoredSystem.Source.FW_WARZONE,
                "is_active": True,
            },
        )
        if created:
            count += 1
    invalidate_monitored_systems_cache()
    return count


class Command(BaseCommand):
    help = "Seed FeedMonitoredSystem from ESI /fw/systems/ (Amarr–Minmatar warzone) or fixture fallback"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fixture-only",
            action="store_true",
            help="Use local fixture only (for CI)",
        )

    def handle(self, *args, **options):
        if options["fixture_only"]:
            count = seed_from_fixture()
        else:
            try:
                count = seed_from_esi()
            except Exception as exc:
                self.stderr.write(
                    f"ESI seed failed ({exc}); using fixture fallback"
                )
                count = seed_from_fixture()
            else:
                if (
                    FeedMonitoredSystem.objects.filter(is_active=True).count()
                    == 0
                ):
                    self.stderr.write(
                        "ESI seed produced no active systems; "
                        "using fixture fallback"
                    )
                    count = seed_from_fixture()
        total = FeedMonitoredSystem.objects.filter(is_active=True).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {count} new systems ({total} active total)"
            )
        )
