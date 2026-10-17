"""New pilots welcomed into the alliance (Advocates tribe)."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from applications.models import EveCorporationApplication
from eveonline.models import EveCharacter
from fleets.models import EveFleetInstanceMember
from groups.models import UserCommunityStatus, UserCommunityStatusHistory
from tribes.reports.queries.common import (
    best_month,
    best_month_since,
    period_window,
    person_rows,
    primary_characters,
)
from tribes.reports.roster import roster_user_ids
from tribes.reports.types import PeriodBounds, ReportScope

# Minmatar Fleet Academy (L3ARN); same id the alliance health page uses.
ACADEMY_CORP_ID = 98741376

# Status rows written for something other than earning full membership.
NOT_A_PROMOTION_REASONS = (
    "No longer Alliance",
    "fix_trial_status_by_affiliation management command",
)

FIRST_FLEET_WINDOW = timedelta(days=7)
WELCOMED_WALL = 8

COLUMNS = ["primary_character_name", "applications_accepted"]


def _accepted():
    # No accepted-at field: updated_at is when the accept was saved.
    return EveCorporationApplication.objects.filter(status="accepted")


def _promotions():
    return UserCommunityStatusHistory.objects.filter(
        from_status=UserCommunityStatus.STATUS_TRIAL,
        to_status=UserCommunityStatus.STATUS_ACTIVE,
    ).exclude(reason__in=NOT_A_PROMOTION_REASONS)


def _first_accepts(start, end) -> dict[int, tuple]:
    """User id -> (accepted at, corporation id) for their first accept."""
    first: dict[int, tuple] = {}
    for user_id, updated_at, corp_id in (
        _accepted()
        .filter(updated_at__gte=start, updated_at__lte=end)
        .order_by("updated_at")
        .values_list("user_id", "updated_at", "corporation_id")
    ):
        first.setdefault(user_id, (updated_at, corp_id))
    return first


def _flew_in_first_week(accepts: dict[int, tuple]) -> int:
    if not accepts:
        return 0
    chars = dict(
        EveCharacter.objects.filter(
            user_id__in=accepts, character_id__isnull=False
        ).values_list("character_id", "user_id")
    )
    earliest = min(at for at, _ in accepts.values())
    flew = set()
    for char_id, join_time in EveFleetInstanceMember.objects.filter(
        character_id__in=chars, join_time__gte=earliest
    ).values_list("character_id", "join_time"):
        user_id = chars.get(char_id)
        accepted_at = accepts[user_id][0]
        if accepted_at <= join_time < accepted_at + FIRST_FLEET_WINDOW:
            flew.add(user_id)
    return len(flew)


def run_advocates_report(
    tribe_group, period: PeriodBounds, scope: ReportScope, params
):
    """Alliance-wide welcome totals; contributors are roster recruiters."""
    start, end = period_window(period)
    accepts = _first_accepts(start, end)
    promoted = set(
        _promotions()
        .filter(changed_at__gte=start, changed_at__lte=end)
        .values_list("user_id", flat=True)
    )

    roster = roster_user_ids(tribe_group)
    by_user: dict[int, dict] = defaultdict(
        lambda: {"applications_accepted": 0}
    )
    for processor in (
        _accepted()
        .filter(
            updated_at__gte=start,
            updated_at__lte=end,
            processed_by_id__in=roster,
        )
        .values_list("processed_by_id", flat=True)
    ):
        by_user[processor]["applications_accepted"] += 1

    totals = {
        "pilots_welcomed": len(accepts),
        "academy_pilots": sum(
            1 for _, corp in accepts.values() if corp == ACADEMY_CORP_ID
        ),
        "full_members": len(promoted),
        "first_fleets": _flew_in_first_week(accepts),
    }
    return person_rows(by_user, "applications_accepted"), totals, COLUMNS


def advocates_highlights(tribe_group, period: PeriodBounds) -> dict:
    start, end = period_window(period)
    recent = list(
        _promotions()
        .filter(changed_at__gte=start, changed_at__lte=end)
        .order_by("-changed_at")
        .values_list("user_id", "changed_at")
    )
    seen: dict = {}
    for user_id, changed_at in recent:
        seen.setdefault(user_id, changed_at)
    wall_users = list(seen)[:WELCOMED_WALL]
    primaries = primary_characters(wall_users)

    welcomed_ever = set(_accepted().values_list("user_id", flat=True))
    still_active = UserCommunityStatus.objects.filter(
        user_id__in=welcomed_ever,
        status__in=(
            UserCommunityStatus.STATUS_ACTIVE,
            UserCommunityStatus.STATUS_TRIAL,
        ),
    ).count()

    first_accept_at: dict[int, object] = {}
    for user_id, updated_at in (
        _accepted()
        .filter(updated_at__gte=best_month_since())
        .order_by("updated_at")
        .values_list("user_id", "updated_at")
    ):
        first_accept_at.setdefault(user_id, updated_at)

    return {
        "welcomed": [
            {
                "character_id": primaries[uid][0],
                "character_name": primaries[uid][1],
                "promoted_at": seen[uid].isoformat(),
            }
            for uid in wall_users
            if uid in primaries
        ],
        "best_month": best_month((at, 1) for at in first_accept_at.values()),
        "all_time": {
            "pilots_welcomed": len(welcomed_ever),
            "still_flying": still_active,
        },
    }
