"""Score the home model against applicants' browser timezones.

The application form records the browser's IANA timezone in its
"- Timezone:" line, which is the best ground truth we have for where a
pilot lives. Run this after changing timezones.inference, and paste the
printed HOME_PROFILES in when the alliance's schedule has moved.
"""

import re
from collections import Counter, defaultdict
from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.management.base import BaseCommand
from django.utils import timezone

from applications.models import EveCorporationApplication
from eveonline.models import EvePlayer
from timezones.activity import load_events
from timezones.brackets import AU, EU, REFERENCE_ZONES, US
from timezones.inference import WINDOW_DAYS, assess

TIMEZONE_LINE = re.compile(r"(?im)^-\s*Timezone:\s*(.+)$")
IANA = re.compile(r"\b([A-Z][a-z]+(?:_[A-Za-z]+)*/[A-Za-z_]+(?:/[A-Za-z_]+)?)")


def application_zones() -> dict[int, tuple[str, str]]:
    """User id -> (IANA zone, region) from their latest application."""
    zones = {}
    for user_id, description, created_at in (
        EveCorporationApplication.objects.order_by("created_at")
        .values_list("user_id", "description", "created_at")
        .iterator()
    ):
        line = TIMEZONE_LINE.search(description or "")
        match = IANA.search(line.group(1)) if line else None
        if not match:
            continue
        try:
            zone = ZoneInfo(match.group(1))
        except (ZoneInfoNotFoundError, ValueError):
            continue
        hours = created_at.astimezone(zone).utcoffset().total_seconds() / 3600
        region = US if hours <= -3 else EU if hours <= 4 else AU
        zones[user_id] = (match.group(1), region)
    return zones


class Command(BaseCommand):
    help = __doc__.splitlines()[0]

    def handle(self, *args, **options):
        zones = application_zones()
        events = load_events(
            zones, timezone.now() - timedelta(days=WINDOW_DAYS)
        )
        declared = dict(
            EvePlayer.objects.filter(user_id__in=zones).values_list(
                "user_id", "prime_time"
            )
        )
        self.stdout.write(
            f"{len(zones)} applicants with a browser timezone, "
            f"{len(events)} with activity in {WINDOW_DAYS} days: "
            f"{dict(Counter(region for _, region in zones.values()))}"
        )
        for minimum in (1, 5, 15, 40):
            scored = Counter()
            for user_id, (_, region) in zones.items():
                pilot_events = events.get(user_id, [])
                if len(pilot_events) < minimum:
                    continue
                scored["pilots"] += 1
                if assess(pilot_events).inferred_home == region:
                    scored["activity"] += 1
                if assess(pilot_events, declared.get(user_id)).home == region:
                    scored["with_declared"] += 1
            if scored["pilots"]:
                self.stdout.write(
                    f">= {minimum:2} events, {scored['pilots']} pilots: "
                    f"activity only {scored['activity'] / scored['pilots']:.0%}, "
                    f"with declared {scored['with_declared'] / scored['pilots']:.0%}"
                )
        self.stdout.write("HOME_PROFILES = {")
        for region in (US, EU):
            self.stdout.write(
                f"    {region}: ({', '.join(f'{v:.4f}' for v in _profile(region, zones, events))}),"
            )
        self.stdout.write("}")


def _profile(region, zones, events):
    """Mean share of play per hour on ``region``'s clock, 10% uniform."""
    totals = defaultdict(float)
    pilots = 0
    zone = REFERENCE_ZONES[region]
    for user_id, (_, truth) in zones.items():
        pilot_events = events.get(user_id)
        if truth != region or not pilot_events:
            continue
        pilots += 1
        for event in pilot_events:
            totals[event.astimezone(zone).hour] += 1 / len(pilot_events)
    if not pilots:
        return [1 / 24] * 24
    return [0.9 * totals[hour] / pilots + 0.1 / 24 for hour in range(24)]
