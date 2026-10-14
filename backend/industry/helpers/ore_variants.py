"""CCP ore-variant mineral scale (II/III/IV-Grade, Brimful, Glistening)."""

from __future__ import annotations

import re

_GRADE_SUFFIX_RE = re.compile(r"\s+(II|III|IV)-Grade$")
_MOON_PREFIX_RE = re.compile(r"^(Brimful|Glistening)\s+")

# Same scale as the Jita ore-buy clamp in buyback.helpers.ore_names.
_ORE_GRADE_YIELD_FACTORS = {"II": 1.05, "III": 1.10, "IV": 1.15}
_ORE_MOON_YIELD_FACTORS = {"Brimful": 1.15, "Glistening": 2.0}


def ore_variant_yield_factor(name: str) -> float:
    """Mineral-content scale vs the base ore. 1.0 for the base type."""
    return split_ore_variant(name)[1]


def split_ore_variant(name: str) -> tuple[str, float]:
    """
    Return ``(base name, factor)``.

    Strips a Compressed prefix, then one grade suffix or moon prefix.
    Base types come back unchanged with factor 1.0.
    """
    rest = name
    if rest.startswith("Compressed "):
        rest = rest[len("Compressed ") :]
    grade = _GRADE_SUFFIX_RE.search(rest)
    if grade:
        base = _GRADE_SUFFIX_RE.sub("", rest)
        return base, _ORE_GRADE_YIELD_FACTORS[grade.group(1)]
    moon = _MOON_PREFIX_RE.match(rest)
    if moon:
        base = _MOON_PREFIX_RE.sub("", rest)
        return base, _ORE_MOON_YIELD_FACTORS[moon.group(1)]
    return rest, 1.0
