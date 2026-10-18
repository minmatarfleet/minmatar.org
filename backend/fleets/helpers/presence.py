"""When a pilot was in a tracked fleet, from the ESI poller's member rows.

The poller keeps one row per pilot per fleet instance and rewrites it on
every pass (fleets.helpers.member_ships.apply_esi_fleet_member):

- ``created_at`` is when the poller first saw the pilot.
- ``join_time`` is copied from ESI on every pass. ESI reports the latest
  join, so it moves forward when a pilot drops and rejoins (about 7% of
  rows), and no new row is written. The earlier of the two is when we first
  saw them.
- ``updated_at`` is rewritten on every pass, so it is the last time we saw
  them.

So ``[first_seen, last_seen]`` covers every moment the pilot was in the
fleet, plus any gap between a drop and a rejoin, which the poller cannot
see. Fleet kill cards and campaign attendance both read presence through
here, so a kill is a fleet kill on the fleet page exactly when it is one on
the campaign board.
"""

from __future__ import annotations

from datetime import datetime, timedelta

# ESI polls the fleet every few minutes, so a pilot can die or get on a mail
# a little before their row is first written or after it was last touched.
JOIN_GRACE = timedelta(minutes=2)
LAST_SEEN_GRACE = timedelta(minutes=5)


def member_window(
    join_time: datetime,
    created_at: datetime | None,
    updated_at: datetime | None,
) -> tuple[datetime, datetime]:
    """``(first_seen, last_seen)`` for one member row."""
    first_seen = join_time
    if created_at is not None:
        first_seen = min(join_time, created_at)
    return first_seen, updated_at or first_seen


def was_present(window: tuple[datetime, datetime], moment: datetime) -> bool:
    """True when ``moment`` falls in the window, with the polling grace."""
    first_seen, last_seen = window
    return first_seen - JOIN_GRACE <= moment <= last_seen + LAST_SEEN_GRACE
