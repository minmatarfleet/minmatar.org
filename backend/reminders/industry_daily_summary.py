"""Build the daily Discord message for industry order overview."""

from __future__ import annotations

from industry.order_summary import get_order_summary_message

MAX_SECTION_LINES = 35


def build_industry_daily_summary_message() -> str:
    """Markdown plain text for Discord (see ``industry.order_summary``)."""
    return get_order_summary_message(max_section_lines=MAX_SECTION_LINES)
