"""Doctrine upkeep and doctrine discipline in fleets (Readiness tribe).

Doctrine-ready pilot counts are not here: EveSkillset has no link to a
doctrine, so the frontend shows those cards as coming soon.
"""

from __future__ import annotations

from collections import defaultdict

from fittings.models import (
    ChangeRequestStatus,
    EveDoctrineChangeRequest,
    EveDoctrineFitting,
    EveFittingChangeRequest,
)
from fleets.models import (
    EveFleet,
    EveFleetInstanceMember,
    EveFleetInstanceMemberShipSnapshot,
)
from tribes.reports.queries.common import period_window, person_rows
from tribes.reports.roster import roster_user_ids
from tribes.reports.types import PeriodBounds, ReportScope

COLUMNS = [
    "primary_character_name",
    "doctrine_changes",
    "changes_proposed",
    "changes_reviewed",
]

CHANGE_REQUEST_MODELS = (EveDoctrineChangeRequest, EveFittingChangeRequest)


def _approved_changes(start, end):
    for model in CHANGE_REQUEST_MODELS:
        yield from model.objects.filter(
            status=ChangeRequestStatus.APPROVED,
            reviewed_at__gte=start,
            reviewed_at__lte=end,
        ).values_list("submitted_by_id", "reviewed_by_id")


def _doctrine_fleet_discipline(start, end) -> tuple[int, int, int]:
    """(doctrine fleets, pilots seen, pilots seen in a doctrine hull)."""
    fleets = dict(
        EveFleet.objects.filter(
            doctrine__isnull=False, start_time__gte=start, start_time__lte=end
        ).values_list("id", "doctrine_id")
    )
    if not fleets:
        return 0, 0, 0
    hulls_by_doctrine: dict[int, set[int]] = defaultdict(set)
    for doctrine_id, ship_id in EveDoctrineFitting.objects.filter(
        doctrine_id__in=set(fleets.values())
    ).values_list("doctrine_id", "fitting__ship_id"):
        hulls_by_doctrine[doctrine_id].add(ship_id)

    members = {
        member_id: (fleet_id, char_id, ship_id)
        for member_id, fleet_id, char_id, ship_id in (
            EveFleetInstanceMember.objects.filter(
                eve_fleet_instance__eve_fleet_id__in=fleets
            ).values_list(
                "id",
                "eve_fleet_instance__eve_fleet_id",
                "character_id",
                "ship_type_id",
            )
        )
    }
    hulls_flown: dict[int, set[int]] = defaultdict(set)
    for (
        member_id,
        ship_id,
    ) in EveFleetInstanceMemberShipSnapshot.objects.filter(
        member_id__in=members
    ).values_list(
        "member_id", "ship_type_id"
    ):
        hulls_flown[member_id].add(ship_id)

    # A pilot counts once per fleet, across every instance of it.
    seen: dict[tuple[int, int], bool] = {}
    for member_id, (fleet_id, char_id, last_ship) in members.items():
        flown = hulls_flown[member_id] | {last_ship}
        in_doctrine = bool(flown & hulls_by_doctrine[fleets[fleet_id]])
        key = (fleet_id, char_id)
        seen[key] = seen.get(key, False) or in_doctrine
    return len(fleets), len(seen), sum(seen.values())


def run_readiness_report(
    tribe_group, period: PeriodBounds, scope: ReportScope, params
):
    start, end = period_window(period)
    roster = roster_user_ids(tribe_group)

    approved = 0
    by_user: dict[int, dict] = defaultdict(
        lambda: {
            "doctrine_changes": 0,
            "changes_proposed": 0,
            "changes_reviewed": 0,
        }
    )
    for submitted_by, reviewed_by in _approved_changes(start, end):
        approved += 1
        if submitted_by in roster:
            by_user[submitted_by]["changes_proposed"] += 1
            by_user[submitted_by]["doctrine_changes"] += 1
        if reviewed_by in roster and reviewed_by != submitted_by:
            by_user[reviewed_by]["changes_reviewed"] += 1
            by_user[reviewed_by]["doctrine_changes"] += 1

    fleets, pilots, in_doctrine = _doctrine_fleet_discipline(start, end)
    totals = {
        "doctrine_updates": approved,
        "doctrine_fleets": fleets,
        "flew_in_doctrine_pct": (
            round(100 * in_doctrine / pilots) if pilots else 0
        ),
    }
    return person_rows(by_user, "doctrine_changes"), totals, COLUMNS
