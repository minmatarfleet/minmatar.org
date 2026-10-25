from typing import List, Optional

from ninja import Schema


class TimezoneTag(Schema):
    """A pilot's timezones as every page shows them: the bracket codes
    (USTZ, EUTZ+, ...) and where they came from, "activity" or "declared".
    No brackets means nothing is known yet."""

    brackets: List[str] = []
    source: Optional[str] = None
