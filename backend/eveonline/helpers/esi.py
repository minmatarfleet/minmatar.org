"""Shared ESI response parsing helpers."""

from datetime import datetime

import pytz
from django.utils import timezone


def parse_esi_date(value):
    """Parse ESI ISO date string (or datetime) to a timezone-aware datetime."""
    if not value:
        return None
    if isinstance(value, datetime):
        return (
            timezone.make_aware(value) if timezone.is_naive(value) else value
        )
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if timezone.is_naive(dt):
        dt = pytz.UTC.localize(dt)
    return dt
