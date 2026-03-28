"""Presentation helpers for industry Discord order summary (plain text / markdown)."""

from __future__ import annotations

from decimal import Decimal

from industry.models import IndustryOrder

BILLION = Decimal("1000000000")


def _pluralize_word(word: str) -> str:
    """Pluralize a single token (lowercase logic, preserve case of suffix heuristically)."""
    if not word:
        return word
    lower = word.lower()
    if len(lower) >= 2 and lower.endswith("s") and not lower.endswith("us"):
        return word
    if lower.endswith("y") and len(lower) > 1 and lower[-2] not in "aeiou":
        return word[:-1] + ("ies" if word[-1] == "y" else "IES")
    if lower.endswith(("ch", "sh")) or lower[-1] in ("x", "s", "z"):
        return word + "es"
    return word + "s"


def pluralize_eve_group_name(name: str) -> str:
    """
    English-ish plural for EVE group labels (pluralize last word, e.g. ``Energy Weapon`` →
    ``Energy Weapons``).
    """
    n = (name or "").strip()
    if not n:
        return n
    parts = n.split()
    parts[-1] = _pluralize_word(parts[-1])
    return " ".join(parts)


def order_location_short_label(order: IndustryOrder) -> str:
    """Short bracket label: ``short_name`` → ``location_name`` → ``Unknown``."""
    loc = order.location
    if loc is None:
        return "Unknown"
    if loc.short_name and str(loc.short_name).strip():
        return str(loc.short_name).strip()
    if loc.location_name and str(loc.location_name).strip():
        return str(loc.location_name).strip()
    return "Unknown"


def format_isk_billions_trimmed(isk: Decimal) -> str:
    """ISK as billions string like ``2`` or ``4.5`` with ``B`` suffix (no `` profit``)."""
    if isk <= 0:
        return "0B"
    billions = isk / BILLION
    text = f"{billions:.2f}".rstrip("0").rstrip(".")
    return f"{text}B"


def format_margin_profit_parenthetical(isk: Decimal) -> str:
    """``(2B profit)`` style from target margin ISK."""
    return f"({format_isk_billions_trimmed(isk)} profit)"
