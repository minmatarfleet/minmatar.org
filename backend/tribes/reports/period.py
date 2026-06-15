"""Parse report period strings (e.g. 30d, 12m)."""

from datetime import timedelta

from django.utils import timezone

from tribes.reports.types import PeriodBounds


def parse_period(period: str) -> PeriodBounds:
    period = (period or "30d").strip().lower()
    today = timezone.now().date()
    if period.endswith("d"):
        days = int(period[:-1])
        start = today - timedelta(days=days)
        return PeriodBounds(label=period, start=start, end=today)
    if period.endswith("m"):
        months = int(period[:-1])
        start = today - timedelta(days=months * 30)
        return PeriodBounds(label=period, start=start, end=today)
    raise ValueError(f"Unsupported period: {period}")
