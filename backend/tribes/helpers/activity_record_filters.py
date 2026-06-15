"""Shared filters for tribe activity record queries."""

from django.db.models import F
from django.db.models.functions import Coalesce


def annotate_event_time(qs):
    """Annotate queryset with event_time = occurred_at or created_at."""
    return qs.annotate(event_time=Coalesce(F("occurred_at"), F("created_at")))


def filter_records_by_period(qs, start=None, end=None):
    """Filter records by event time (occurred_at when set, else created_at)."""
    if start is None and end is None:
        return qs
    qs = annotate_event_time(qs)
    if start is not None:
        qs = qs.filter(event_time__gte=start)
    if end is not None:
        qs = qs.filter(event_time__lte=end)
    return qs
