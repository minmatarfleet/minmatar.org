"""Shared ESI response parsing helpers."""

from datetime import datetime
from decimal import Decimal

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


def _decimal(value):
    return None if value is None else Decimal(str(value))


def esi_contract_defaults(raw: dict) -> dict:
    """Model fields for one ESI contract row (character or corporation).

    The owner foreign key is the caller's to add.
    """
    return {
        "type": raw.get("type", ""),
        "status": raw.get("status", ""),
        "availability": raw.get("availability", ""),
        "issuer_id": raw.get("issuer_id"),
        "issuer_corporation_id": raw.get("issuer_corporation_id"),
        "assignee_id": raw.get("assignee_id"),
        "acceptor_id": raw.get("acceptor_id"),
        "for_corporation": raw.get("for_corporation", False),
        "date_issued": parse_esi_date(raw.get("date_issued")),
        "date_expired": parse_esi_date(raw.get("date_expired")),
        "date_accepted": parse_esi_date(raw.get("date_accepted")),
        "date_completed": parse_esi_date(raw.get("date_completed")),
        "days_to_complete": raw.get("days_to_complete"),
        "price": _decimal(raw.get("price")),
        "reward": _decimal(raw.get("reward")),
        "collateral": _decimal(raw.get("collateral")),
        "buyout": _decimal(raw.get("buyout")),
        "volume": _decimal(raw.get("volume")),
        "start_location_id": raw.get("start_location_id"),
        "end_location_id": raw.get("end_location_id"),
        "title": raw.get("title", ""),
    }


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
