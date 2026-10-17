"""The week's objective rows: one per target, how far along, which way.

The website's objectives table and the desktop Campaigns window both draw
these rows, so they are built here once: which rows there are, their order,
the progress figure and its move since the week opened and over the last
day, and whether the system changed hands. The surfaces only format them.

Every progress figure reads "higher is better", on 0-100. Complex objectives
are measured in victory points against the flip threshold; defending, the bar
is how far the attackers are from flipping it, so it is inverted. Advantage
objectives are the advantage level; destroying, it is inverted. Structure
objectives are the reports against the target.

Before the week has targets, each FW system gets one row from its own goal,
so neither surface asks for nothing.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone

from campaigns.helpers import campaign_week_start, week_bounds
from campaigns.models import (
    Campaign,
    CampaignAdvantageReading,
    CampaignSystemSnapshot,
    CampaignWeekTarget,
    SystemGoal,
)
from campaigns.services import advantage, plan
from feed.constants import FACTION_AMARR, FACTION_MINMATAR

FACTIONS = {FACTION_MINMATAR: "minmatar", FACTION_AMARR: "amarr"}
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
# Within a priority, the objectives we are losing come first.
PACE_RANK = {"behind": 0, "on_pace": 1, "ahead": 2}

METRIC_OBJECTIVES = {
    CampaignWeekTarget.Metric.VICTORY_POINTS: "capture_complexes",
    CampaignWeekTarget.Metric.DAYS_UNDER_LINE: "defend_complexes",
    CampaignWeekTarget.Metric.ADVANTAGE: "gain_advantage",
    CampaignWeekTarget.Metric.ADVANTAGE_GAIN: "gain_advantage",
    CampaignWeekTarget.Metric.ADVANTAGE_MAINTAIN: "hold_advantage",
    CampaignWeekTarget.Metric.ADVANTAGE_DESTROY: "destroy_advantage",
    CampaignWeekTarget.Metric.STRUCTURES_REPORTED: "report_structures",
}
COMPLEX_OBJECTIVES = ("capture_complexes", "defend_complexes")
ADVANTAGE_OBJECTIVES = (
    "gain_advantage",
    "hold_advantage",
    "destroy_advantage",
)
OFFENSIVE_GOALS = (SystemGoal.TAKE, SystemGoal.PRESSURE, SystemGoal.DISRUPT)


def weekly_rows(campaign: Campaign) -> list[dict]:
    """The week's objective rows in their one agreed order.

    Highest priority first. Within a priority, target rows run losing first
    (behind, on pace, ahead); rows from goals alone run hottest contest
    first. Then by system name, so the order never depends on the database.
    """
    systems = {
        system.id: system for system in _systems_with_readings(campaign)
    }
    targets = list(
        CampaignWeekTarget.objects.filter(
            campaign_system_id__in=systems.keys(),
            week_start=campaign_week_start(),
            metric__in=METRIC_OBJECTIVES.keys(),
        )
    )
    pairs = [
        (systems[target.campaign_system_id], target) for target in targets
    ]
    if not pairs:
        pairs = [
            (system, None)
            for system in systems.values()
            if system.is_fw_objective
        ]

    snapshots = CampaignSystemSnapshot.objects.in_bulk(
        [
            snapshot_id
            for system, _ in pairs
            for snapshot_id in (
                system.latest_snapshot,
                system.day_ago_snapshot,
                system.week_open_snapshot,
            )
            if snapshot_id
        ]
    )
    readings = CampaignAdvantageReading.objects.in_bulk(
        [
            system.day_ago_reading
            for system, _ in pairs
            if system.day_ago_reading
        ]
    )
    rows = [
        _row(system, target, snapshots, readings) for system, target in pairs
    ]
    return sorted(rows, key=_order)


def _order(row: dict):
    priority = PRIORITY_RANK.get(row["priority"], 1)
    if row["target_id"] is None:
        # No pace before targets exist: the fight that needs people leads.
        contested = row["contested_percent"] or 0
        return (priority, 0, -contested, row["name"], 0)
    return (
        priority,
        PACE_RANK.get(row["pace"], 1),
        0,
        row["name"],
        row["target_id"],
    )


def _systems_with_readings(campaign: Campaign):
    """Live systems, each with the ids of its latest, 24h-old and week-open
    snapshot and its 24h-old advantage reading, in one query.

    The week opens on the last snapshot before it began; with none, on the
    first inside it.
    """
    day_ago = timezone.now() - timedelta(hours=24)
    week_open = week_bounds(campaign_week_start())[0]
    snapshots = CampaignSystemSnapshot.objects.filter(
        campaign_system=OuterRef("pk")
    ).order_by("-captured_at")
    readings = CampaignAdvantageReading.objects.filter(
        campaign_system=OuterRef("pk"),
        status="accepted",
        reported_at__lte=day_ago,
    ).order_by("-reported_at")
    return (
        campaign.systems.filter(retired_at__isnull=True)
        .select_related("advantage_state")
        .annotate(
            latest_snapshot=Subquery(snapshots.values("id")[:1]),
            day_ago_snapshot=Subquery(
                snapshots.filter(captured_at__lte=day_ago).values("id")[:1]
            ),
            day_ago_reading=Subquery(readings.values("id")[:1]),
            week_open_snapshot=Coalesce(
                Subquery(
                    snapshots.filter(captured_at__lt=week_open).values("id")[
                        :1
                    ]
                ),
                Subquery(
                    snapshots.filter(captured_at__gte=week_open)
                    .order_by("captured_at")
                    .values("id")[:1]
                ),
            ),
        )
    )


def _goal_objective(goal: str) -> str:
    if goal in OFFENSIVE_GOALS:
        return "capture_complexes"
    if goal == SystemGoal.RECON:
        return "report_structures"
    return "defend_complexes"


def _row(system, target, snapshots: dict, readings: dict) -> dict:
    objective = (
        METRIC_OBJECTIVES[target.metric]
        if target
        else _goal_objective(system.goal)
    )
    latest = snapshots.get(system.latest_snapshot)
    row = {
        "target_id": target.id if target else None,
        "system_id": system.id,
        "name": system.name,
        "solar_system_id": system.solar_system_id,
        "priority": system.priority,
        "holder": FACTIONS.get(latest.occupier_faction_id) if latest else None,
        "objective": objective,
        "pace": target.pace if target else None,
        "proposed": target.proposed if target else False,
        "progress_percent": None,
        "change_week": None,
        "change_24h": None,
        "flipped": None,
        "contested_percent": latest.contested_percent if latest else None,
        "victory_points": latest.victory_points if latest else None,
        "victory_points_threshold": (
            latest.victory_points_threshold if latest else None
        ),
        "advantage_level": None,
        "structures_reported": None,
        "structures_target": None,
    }
    if objective in COMPLEX_OBJECTIVES:
        row.update(
            _complex(
                objective,
                latest,
                snapshots.get(system.day_ago_snapshot),
                snapshots.get(system.week_open_snapshot),
            )
        )
    elif objective in ADVANTAGE_OBJECTIVES:
        row.update(
            _advantage(
                objective,
                advantage.card_for(system),
                readings.get(system.day_ago_reading),
                target,
            )
        )
    elif target:
        goal = target.target or 1
        row["progress_percent"] = _clamp(target.progress / goal * 100)
        row["structures_reported"] = target.progress
        row["structures_target"] = target.target
    return row


def _complex(objective: str, latest, day_ago, week_open) -> dict:
    """Victory points against the system's flip threshold.

    The week's move runs from where it opened. A system that changed hands
    this week has no move: the contest reset, so the flip is the news.
    """
    if latest is None:
        return {}
    defend = objective == "defend_complexes"

    def bar(snapshot):
        contested = _clamp(snapshot.contested_percent)
        return 100 - contested if defend else contested

    now = bar(latest)
    flipped = (
        plan.flip_outcome(
            week_open.occupier_faction_id, latest.occupier_faction_id
        )
        if week_open
        else None
    )
    return {
        "progress_percent": now,
        "change_24h": now - bar(day_ago) if day_ago else None,
        "change_week": (
            now - bar(week_open) if week_open and not flipped else None
        ),
        "flipped": flipped,
    }


def _advantage(objective: str, card: dict, day_ago, target) -> dict:
    """Our advantage level, or for destroy, how far theirs has fallen.

    The week's move is from the target's baseline, the level it opened at:
    ours for gain and hold, theirs for destroy. Without a reading of its own
    the level is the target's last measured progress.
    """
    destroy = objective == "destroy_advantage"
    key = "enemy_pct" if destroy else "our_pct"
    level = card[key]
    if level is None and target is not None:
        level = target.progress
    if level is None:
        return {}

    def bar(value):
        return _clamp(100 - value if destroy else value)

    was = getattr(day_ago, key) if day_ago else None
    return {
        "advantage_level": level,
        "progress_percent": bar(level),
        "change_24h": bar(level) - bar(was) if was is not None else None,
        "change_week": (
            bar(level) - bar(target.baseline)
            if target is not None and target.baseline is not None
            else None
        ),
    }


def _clamp(value: float) -> float:
    return min(100.0, max(0.0, float(value)))
