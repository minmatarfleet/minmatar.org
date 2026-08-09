"""Shared ESI response parsing helpers."""

from datetime import datetime

import pytz
from django.utils import timezone
from esi.exceptions import ESIErrorLimitException


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


def is_esi_error_limited_response(response) -> bool:
    """True when ESI error budget is exhausted (HTTP 420 / ESIErrorLimitException)."""
    if getattr(response, "response_code", None) == 420:
        return True
    return isinstance(
        getattr(response, "response", None), ESIErrorLimitException
    )


def raise_if_esi_error_limited(response) -> None:
    """Re-raise ESIErrorLimitException when the response indicates error-limit."""
    if not is_esi_error_limited_response(response):
        return
    if isinstance(response.response, ESIErrorLimitException):
        raise response.response
    raise ESIErrorLimitException()
