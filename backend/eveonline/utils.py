"""
EVE Online / ESI utilities.
"""

from datetime import time

from django.utils import timezone

# Daily ESI downtime window (UTC)
ESI_DOWNTIME_START = time(11, 0)  # 11:00 UTC
ESI_DOWNTIME_END = time(11, 15)  # 11:15 UTC


def get_esi_downtime_countdown() -> int:
    """
    Return seconds to wait until we're past the daily ESI downtime window (11:00–11:15 UTC).
    Returns 0 if we're already outside the window.
    """
    now = timezone.now()
    if now.tzinfo is None:
        now = timezone.make_aware(now)
    utc_now = timezone.localtime(now, timezone.utc)

    if ESI_DOWNTIME_START <= utc_now.time() < ESI_DOWNTIME_END:
        end_today = utc_now.replace(
            hour=ESI_DOWNTIME_END.hour,
            minute=ESI_DOWNTIME_END.minute,
            second=0,
            microsecond=0,
        )
        delta = end_today - utc_now
        return max(0, int(delta.total_seconds()))
    return 0
