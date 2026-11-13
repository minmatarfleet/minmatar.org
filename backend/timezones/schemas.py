from typing import List, Optional

from ninja import Schema


class TimezoneTag(Schema):
    """A pilot's timezones as every page shows them: the bracket codes
    (USTZ, EUTZ+, ...) and where they came from, "activity" or "declared".
    No brackets means nothing is known yet.

    ``secondary`` are the brackets outside the pilot's home region (a US
    pilot who also flies EU evenings), and ``weekend`` the brackets they
    play almost only on Friday to Sunday evenings. Both are subsets of
    ``brackets``; pages show them muted."""

    brackets: List[str] = []
    source: Optional[str] = None
    secondary: List[str] = []
    weekend: List[str] = []
