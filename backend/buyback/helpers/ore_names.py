"""Compressed-ore base names for buyback variant grouping."""

from __future__ import annotations

import re

BUYBACK_ORE_BASES = frozenset(
    {
        "Veldspar",
        "Scordite",
        "Pyroxeres",
        "Plagioclase",
        "Omber",
        "Kernite",
        "Zeolites",
        "Sylvite",
        "Bitumens",
        "Coesite",
        "Hedbergite",
        "Hemorphite",
        "Jaspet",
        "Gneiss",
        "Crokite",
        "Dark Ochre",
        "Mordunium",
        "Ytirium",
        "Eifyrium",
        "Ducinium",
        "Griemeer",
    }
)

_GRADE_SUFFIX_RE = re.compile(r"\s+(II|III|IV)-Grade$")
_MOON_PREFIX_RE = re.compile(r"^(Brimful|Glistening)\s+")


def compressed_buyback_ore_base(name: str) -> str | None:
    """Return the buyback ore family for a Compressed * type, if any."""
    if not name.startswith("Compressed "):
        return None
    rest = name[len("Compressed ") :]
    rest = _GRADE_SUFFIX_RE.sub("", rest)
    rest = _MOON_PREFIX_RE.sub("", rest)
    return rest if rest in BUYBACK_ORE_BASES else None
