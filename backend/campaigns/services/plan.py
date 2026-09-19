"""The weekly plan and the three orders a pilot gets each day.

Operators do not write objectives. Each system carries one long arc, set once
from the goal and the dates. Every Thursday the plan proposes a target per
system from that arc and last week's momentum, and the day's orders are then
derived from whatever gap the week still has.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from django.db.models import Sum
from django.utils import timezone

from campaigns.constants import (
    DEFAULT_ORDER_POINTS,
    DEFENSIVE_PLEX_CONTEST_THRESHOLD,
    MIN_WEEKLY_VP_TARGET,
    MOMENTUM_BEST_WEEK_CAP,
    MOMENTUM_FACTOR,
)
from campaigns.helpers import campaign_day, campaign_week_start, week_bounds
from campaigns.models import (
    Campaign,
    CampaignDailyOrder,
    CampaignOrderProgress,
    CampaignParticipantDay,
    CampaignSystem,
    CampaignSystemSnapshot,
    CampaignWeekTarget,
    SystemGoal,
)
from campaigns.services import advantage

logger = logging.getLogger(__name__)


def propose_week(campaign: Campaign, week_start: date | None = None) -> int:
    """Propose one target per system. An operator accepts or nudges it."""
    week_start = week_start or campaign_week_start()
    proposed = 0

    for campaign_system in campaign.systems.filter(retired_at__isnull=True):
        arc = getattr(campaign_system, "arc", None)
        if campaign_system.goal == SystemGoal.CAPTURE:
            metric = CampaignWeekTarget.Metric.VICTORY_POINTS
            target = _capture_target(campaign_system, week_start)
        elif campaign_system.goal == SystemGoal.DEFEND:
            metric = CampaignWeekTarget.Metric.DAYS_UNDER_LINE
            target = 7.0
        else:
            continue

        last_week = _actual_last_week(campaign_system, week_start, metric)

        row, created = CampaignWeekTarget.objects.get_or_create(
            campaign_system=campaign_system,
            week_start=week_start,
            metric=metric,
            defaults={
                "target": target,
                "proposed": True,
                "last_week_actual": last_week,
            },
        )
        if created:
            proposed += 1
        elif row.proposed:
            row.target = target
            row.last_week_actual = last_week
            row.save(update_fields=["target", "last_week_actual"])

        if arc and arc.due_at:
            row.projected_arc_date = _project_arc_date(campaign_system, row)
            row.save(update_fields=["projected_arc_date"])

    return proposed


def _capture_target(
    campaign_system: CampaignSystem, week_start: date
) -> float:
    """Last week's gain times 1.2, floored so it is reachable, capped so a
    good week does not set an impossible bar."""
    history = _weekly_gains(campaign_system, weeks=6)
    last_gain = history[-1] if history else 0.0
    best = max(history) if history else 0.0

    target = max(last_gain * MOMENTUM_FACTOR, MIN_WEEKLY_VP_TARGET)
    if best:
        target = min(target, best * MOMENTUM_BEST_WEEK_CAP)

    arc = getattr(campaign_system, "arc", None)
    if arc and arc.due_at:
        remaining = _vp_remaining(campaign_system)
        weeks_left = max(
            1,
            ((arc.due_at.date() - week_start).days + 6) // 7,
        )
        needed = remaining / weeks_left
        # If the arc has slipped, raise the ask gently rather than all at once.
        target = max(target, min(needed, target * 1.5))

    return round(target)


def _weekly_gains(
    campaign_system: CampaignSystem, weeks: int = 6
) -> list[float]:
    gains = []
    for index in range(weeks, 0, -1):
        start = campaign_week_start() - timedelta(weeks=index)
        window_start, window_end = week_bounds(start)
        first = (
            CampaignSystemSnapshot.objects.filter(
                campaign_system=campaign_system,
                captured_at__gte=window_start,
                captured_at__lt=window_end,
            )
            .order_by("captured_at")
            .first()
        )
        last = (
            CampaignSystemSnapshot.objects.filter(
                campaign_system=campaign_system,
                captured_at__gte=window_start,
                captured_at__lt=window_end,
            )
            .order_by("-captured_at")
            .first()
        )
        if first and last:
            gains.append(max(0.0, last.victory_points - first.victory_points))
    return gains


def _vp_remaining(campaign_system: CampaignSystem) -> float:
    snapshot = (
        CampaignSystemSnapshot.objects.filter(campaign_system=campaign_system)
        .order_by("-captured_at")
        .first()
    )
    if not snapshot or not snapshot.victory_points_threshold:
        return MIN_WEEKLY_VP_TARGET
    return max(
        0.0, snapshot.victory_points_threshold - snapshot.victory_points
    )


def _actual_last_week(campaign_system, week_start, metric) -> float:
    previous = CampaignWeekTarget.objects.filter(
        campaign_system=campaign_system,
        week_start=week_start - timedelta(days=7),
        metric=metric,
    ).first()
    return previous.progress if previous else 0.0


def _project_arc_date(campaign_system, row) -> date | None:
    remaining = _vp_remaining(campaign_system)
    if not row.target:
        return None
    weeks = remaining / row.target
    return campaign_week_start() + timedelta(weeks=max(1, round(weeks)))


def update_week_progress(campaign: Campaign) -> int:
    """Refresh progress and pace so the cards read on pace, behind or ahead."""
    week_start = campaign_week_start()
    window_start, window_end = week_bounds(week_start)
    now = timezone.now()
    elapsed = max(
        0.0, min(1.0, (now - window_start) / (window_end - window_start))
    )

    updated = 0
    for row in CampaignWeekTarget.objects.filter(
        campaign_system__campaign=campaign, week_start=week_start
    ).select_related("campaign_system"):
        if row.metric == CampaignWeekTarget.Metric.VICTORY_POINTS:
            # Baseline is the last reading before the week opened; only when
            # there is none do we fall back to the first reading inside it.
            first = (
                CampaignSystemSnapshot.objects.filter(
                    campaign_system=row.campaign_system,
                    captured_at__lt=window_start,
                )
                .order_by("-captured_at")
                .first()
                or CampaignSystemSnapshot.objects.filter(
                    campaign_system=row.campaign_system,
                    captured_at__gte=window_start,
                )
                .order_by("captured_at")
                .first()
            )
            last = (
                CampaignSystemSnapshot.objects.filter(
                    campaign_system=row.campaign_system,
                    captured_at__gte=window_start,
                )
                .order_by("-captured_at")
                .first()
            )
            row.progress = (
                max(0.0, last.victory_points - first.victory_points)
                if first and last
                else 0.0
            )
        else:
            arc = getattr(row.campaign_system, "arc", None)
            ceiling = arc.contest_ceiling if arc else 25.0
            days_under = 0
            for offset in range(7):
                day_start = window_start + timedelta(days=offset)
                if day_start > now:
                    break
                worst = (
                    CampaignSystemSnapshot.objects.filter(
                        campaign_system=row.campaign_system,
                        captured_at__gte=day_start,
                        captured_at__lt=day_start + timedelta(days=1),
                    )
                    .order_by("-contested_percent")
                    .first()
                )
                if worst and worst.contested_percent <= ceiling:
                    days_under += 1
            row.days_under_line = days_under
            row.progress = float(days_under)

        row.pace_expected = row.target * elapsed
        row.save(
            update_fields=["progress", "pace_expected", "days_under_line"]
        )
        updated += 1

    return updated


def generate_orders(campaign: Campaign, day: date | None = None) -> int:
    """Three small orders per pilot, derived from the week's remaining gap."""
    day = day or campaign_day()
    if CampaignDailyOrder.objects.filter(campaign=campaign, day=day).exists():
        return 0

    week_start = campaign_week_start()
    targets = list(
        CampaignWeekTarget.objects.filter(
            campaign_system__campaign=campaign, week_start=week_start
        ).select_related("campaign_system")
    )

    days_left = max(1, 7 - (day - week_start).days if day >= week_start else 7)
    active_pilots = max(
        1,
        CampaignParticipantDay.objects.filter(
            campaign=campaign, day__gte=week_start, active=True
        )
        .values("user_id")
        .distinct()
        .count(),
    )

    created = 0
    pool = dict(DEFAULT_ORDER_POINTS)
    pool.update(campaign.order_pool or {})

    for target in targets:
        gap = max(0.0, target.target - target.progress)
        share = gap / days_left / active_pilots if gap else 0.0
        gap_share_pct = (
            (share / target.target * 100.0) if target.target else 0.0
        )
        system = target.campaign_system

        if system.goal == SystemGoal.CAPTURE:
            created += _make_order(
                campaign,
                day,
                CampaignDailyOrder.Kind.PLEX,
                pool["plex"],
                system,
                {"count": 2, "system": system.name},
                gap_share_pct,
            )
            created += _make_order(
                campaign,
                day,
                CampaignDailyOrder.Kind.KILL,
                pool["kill"],
                system,
                {"count": 1, "system": system.name},
                gap_share_pct / 2,
            )
        else:
            state = advantage.state_for(system)
            arc = getattr(system, "arc", None)
            floor = arc.advantage_floor if arc else 0.0
            net = state.get("net_pct")
            if net is None or net < floor:
                created += _make_order(
                    campaign,
                    day,
                    CampaignDailyOrder.Kind.ADVANTAGE_SITE,
                    pool["advantage_site"],
                    system,
                    {"system": system.name},
                    gap_share_pct,
                )
            snapshot = (
                CampaignSystemSnapshot.objects.filter(campaign_system=system)
                .order_by("-captured_at")
                .first()
            )
            if snapshot and snapshot.contested_percent >= (
                DEFENSIVE_PLEX_CONTEST_THRESHOLD
            ):
                created += _make_order(
                    campaign,
                    day,
                    CampaignDailyOrder.Kind.PLEX,
                    pool["plex"],
                    system,
                    {"count": 1, "system": system.name, "defensive": True},
                    gap_share_pct,
                )

    # Always something to do that does not depend on the plan.
    created += _make_order(
        campaign,
        day,
        CampaignDailyOrder.Kind.STANDING_FLEET,
        pool["standing_fleet"],
        None,
        {"minutes": 30},
        0,
    )
    created += _make_order(
        campaign,
        day,
        CampaignDailyOrder.Kind.GANG,
        pool["gang"],
        None,
        {},
        0,
    )

    return created


def _make_order(campaign, day, kind, points, system, params, gap_share_pct):
    CampaignDailyOrder.objects.create(
        campaign=campaign,
        day=day,
        kind=kind,
        points=points,
        params=params,
        campaign_system=system,
        gap_share_pct=round(gap_share_pct, 2),
        scope="all",
    )
    return 1


def orders_for(
    campaign: Campaign, user, day: date | None = None
) -> list[dict]:
    """Today's orders with this pilot's progress attached."""
    day = day or campaign_day()
    orders = CampaignDailyOrder.objects.filter(
        campaign=campaign, day=day
    ).select_related("campaign_system")

    progress = {
        row.order_id: row
        for row in CampaignOrderProgress.objects.filter(
            order__campaign=campaign, order__day=day, user=user
        )
    }

    result = []
    for order in orders:
        row = progress.get(order.id)
        result.append(
            {
                "id": order.id,
                "kind": order.kind,
                "label": order.get_kind_display(),
                "params": order.params,
                "points": order.points,
                "system": (
                    order.campaign_system.name
                    if order.campaign_system
                    else None
                ),
                "gap_share_pct": order.gap_share_pct,
                "progress": row.progress if row else 0,
                "completed": bool(row and row.completed_at),
            }
        )
    return result


def evaluate_orders(campaign: Campaign, day: date | None = None) -> int:
    """Mark orders done from what we already attributed. Never self-reported."""
    day = day or campaign_day()
    orders = list(
        CampaignDailyOrder.objects.filter(campaign=campaign, day=day)
    )
    if not orders:
        return 0

    day_rows = CampaignParticipantDay.objects.filter(
        campaign=campaign, day=day
    )
    completed = 0

    for row in day_rows:
        for order in orders:
            achieved = _order_progress(order, row)
            required = float(order.params.get("count", 1) or 1)
            progress_row, _ = CampaignOrderProgress.objects.get_or_create(
                order=order, user_id=row.user_id
            )
            progress_row.progress = min(achieved, required)
            if achieved >= required and not progress_row.completed_at:
                progress_row.completed_at = timezone.now()
                completed += 1
            progress_row.save()

    return completed


def _order_progress(order: CampaignDailyOrder, row) -> float:
    kind = order.kind
    mapping = {
        CampaignDailyOrder.Kind.KILL: row.kills,
        CampaignDailyOrder.Kind.GANG_KILL: row.gang_kills,
        CampaignDailyOrder.Kind.PLEX: row.complexes,
        CampaignDailyOrder.Kind.ADVANTAGE_SITE: row.advantage_sites,
        CampaignDailyOrder.Kind.SUPPLY_CACHE: row.supply_caches,
        CampaignDailyOrder.Kind.ADVANTAGE_REPORT: row.advantage_readings,
        CampaignDailyOrder.Kind.FLEET: row.fleets_attended,
        CampaignDailyOrder.Kind.STANDING_FLEET: (
            1 if row.standing_fleet_day else 0
        ),
        CampaignDailyOrder.Kind.FIRST_KILL: row.kills,
        CampaignDailyOrder.Kind.FIRST_PLEX: row.complexes,
    }
    return float(mapping.get(kind, 0))


def draft_commander_order(campaign: Campaign) -> str:
    """One line above the orders, written from the plan when nobody writes it."""
    week_start = campaign_week_start()
    behind = [
        row
        for row in CampaignWeekTarget.objects.filter(
            campaign_system__campaign=campaign, week_start=week_start
        ).select_related("campaign_system")
        if row.pace == "behind"
    ]
    if behind:
        names = ", ".join(row.campaign_system.name for row in behind[:2])
        return f"We are behind in {names}. Plex there first tonight."

    totals = CampaignParticipantDay.objects.filter(
        campaign=campaign, day__gte=week_start
    ).aggregate(kills=Sum("kills"), complexes=Sum("complexes"))
    return (
        f"On pace: {totals['kills'] or 0} kills and "
        f"{totals['complexes'] or 0} complexes this week. Keep it rolling."
    )
