"""Which timezone seat a group chief sits in (US, EU, AU).

Kept free of model imports so migrations can use it with historical models.
"""

from __future__ import annotations

REGIONS = ("US", "EU", "AU")
LABELS = {"US": "USTZ", "EU": "EUTZ", "AU": "AUTZ"}
# A pilot with no known timezone lands here until someone moves them.
FALLBACK_REGION = "US"


def clean_region(value) -> str | None:
    """``"eu"``/``"EUTZ"``/``"EUTZ+"`` -> ``"EU"``; anything else -> None."""
    text = str(value or "").strip().upper()
    code = text[:2]
    return code if code in REGIONS else None


def home_region(home: str | None, brackets=None) -> str | None:
    """A pilot's region from their PilotTimezone home, else first bracket."""
    region = clean_region(home)
    if region:
        return region
    for code in brackets or ():
        region = clean_region(code)
        if region:
            return region
    return None


def pick_region(preferred: str | None, taken) -> str | None:
    """``preferred`` if free, else the first free seat, else None."""
    taken = set(taken)
    if preferred in REGIONS and preferred not in taken:
        return preferred
    for region in REGIONS:
        if region not in taken:
            return region
    return None
