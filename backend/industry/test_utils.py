"""Test helpers for industry models."""

from __future__ import annotations

from industry.helpers.public_short_code import (
    pick_unique_public_short_code_among_actives,
)
from industry.models import IndustryOrder


def create_industry_order(**kwargs) -> IndustryOrder:
    """Like ``IndustryOrder.objects.create`` but assigns ``public_short_code`` if omitted."""
    if "public_short_code" not in kwargs:
        kwargs["public_short_code"] = (
            pick_unique_public_short_code_among_actives()
        )
    return IndustryOrder.objects.create(**kwargs)
