"""Shared freight contract display helpers (API responses and CSV export)."""

from eveonline.helpers.corporation_contract_display import (
    acceptor_display,
    completed_by_display,
    corp_display_name,
    display_character,
    resolve_characters,
    resolve_location_names,
)
from freight.models import FREIGHT_CORPORATION_ID

FREIGHT_CORP_FALLBACK_NAME = "Freight corp"


def freight_corp_display_name():
    return corp_display_name(
        FREIGHT_CORPORATION_ID, FREIGHT_CORP_FALLBACK_NAME
    )


__all__ = [
    "FREIGHT_CORP_FALLBACK_NAME",
    "acceptor_display",
    "completed_by_display",
    "display_character",
    "freight_corp_display_name",
    "resolve_characters",
    "resolve_location_names",
]
