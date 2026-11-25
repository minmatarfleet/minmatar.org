"""Alts on one account that left together are answered as one row (design 04)."""

from exits.helpers.departures import GRACE
from exits.models import Departure


def group(departures: list[Departure]) -> list[list[Departure]]:
    """Newest first. A group shares an account and left within ``GRACE`` of
    its first departure; characters with no account are groups of one."""
    groups: list[list[Departure]] = []
    open_groups: dict[int, list[Departure]] = {}
    for departure in sorted(
        departures, key=lambda d: (d.first_missing_at, d.pk), reverse=True
    ):
        if departure.user_id is None:
            groups.append([departure])
            continue
        current = open_groups.get(departure.user_id)
        if (
            current is not None
            and current[0].first_missing_at - departure.first_missing_at
            <= GRACE
        ):
            current.append(departure)
            continue
        current = [departure]
        open_groups[departure.user_id] = current
        groups.append(current)
    return groups
