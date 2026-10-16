"""The desktop app's Campaigns window: where each system stands, who is out.

The window is glanced at over the game, so it carries one progress figure
per objective and the 24h move, never the contest breakdown. Complex
objectives are measured in victory points; advantage objectives in the
advantage level. Every progress figure reads "higher is better", so a
defensive or destroy objective is inverted before it gets here.

Every desktop app polls this once a minute, so it is built from a handful
of queries and served from the cache: one build per campaign per minute,
whoever asks.
"""

from __future__ import annotations

import time
from datetime import timedelta

from django.db.models import OuterRef, Q, Subquery
from django.utils import timezone

from campaigns.helpers import campaign_week_start
from campaigns.models import (
    ADVANTAGE_SITE_KINDS,
    Campaign,
    CampaignAdvantageReading,
    CampaignKillmailParticipant,
    CampaignSiteCompletion,
    CampaignStatus,
    CampaignSystemSnapshot,
    CampaignWeekTarget,
    KillmailOutcome,
    SiteKind,
    SystemGoal,
)
from campaigns.services import advantage, plan
from eveonline.helpers.corporations.safe_cache import (
    cache_add,
    cache_delete,
    cache_get,
    cache_set,
)
from eveonline.models import EveCharacter, EvePlayer
from feed.constants import FACTION_AMARR, FACTION_MINMATAR
from fleets.models import EveFleetInstanceMember

ACTIVE_WINDOW_MINUTES = 60
FRESH_SECONDS = 60
# A stale copy is served while one request rebuilds it, so a minute's worth
# of desktop apps never all rebuild at once when the fresh copy lapses.
STALE_SECONDS = 10 * 60
REBUILD_LOCK_SECONDS = 30
CACHE_KEY = "campaigns:overlay:{campaign_id}"
LOCK_KEY = "campaigns:overlay:{campaign_id}:rebuilding"

FACTIONS = {FACTION_MINMATAR: "minmatar", FACTION_AMARR: "amarr"}
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}

OBJECTIVE_LABELS = {
    "capture_complexes": "Capture complexes",
    "defend_complexes": "Defend complexes",
    "gain_advantage": "Gain advantage",
    "hold_advantage": "Hold advantage",
    "destroy_advantage": "Destroy advantage",
}
METRIC_OBJECTIVES = {
    CampaignWeekTarget.Metric.VICTORY_POINTS: "capture_complexes",
    CampaignWeekTarget.Metric.DAYS_UNDER_LINE: "defend_complexes",
    CampaignWeekTarget.Metric.ADVANTAGE: "gain_advantage",
    CampaignWeekTarget.Metric.ADVANTAGE_GAIN: "gain_advantage",
    CampaignWeekTarget.Metric.ADVANTAGE_MAINTAIN: "hold_advantage",
    CampaignWeekTarget.Metric.ADVANTAGE_DESTROY: "destroy_advantage",
}
COMPLEX_OBJECTIVES = ("capture_complexes", "defend_complexes")
OFFENSIVE_GOALS = (SystemGoal.TAKE, SystemGoal.PRESSURE, SystemGoal.DISRUPT)


def pick_campaign(user) -> Campaign | None:
    """The live campaign the pilot is enlisted in, else the newest live one."""
    live = Campaign.objects.filter(status=CampaignStatus.ACTIVE).order_by(
        "-start_at"
    )
    enlisted = live.filter(
        enlistments__user=user, enlistments__status="active"
    ).first()
    return enlisted or live.first()


def overlay(campaign: Campaign) -> dict:
    """Nothing in here depends on who asks, so one copy serves every window."""
    key = CACHE_KEY.format(campaign_id=campaign.id)
    lock = LOCK_KEY.format(campaign_id=campaign.id)
    cached = cache_get(key)
    if cached is not None:
        if cached["fresh_until"] > time.time():
            return cached["payload"]
        if not cache_add(lock, 1, REBUILD_LOCK_SECONDS):
            return cached["payload"]  # someone else is rebuilding it
    payload = build(campaign)
    cache_set(
        key,
        {"fresh_until": time.time() + FRESH_SECONDS, "payload": payload},
        STALE_SECONDS,
    )
    cache_delete(lock)
    return payload


def build(campaign: Campaign) -> dict:
    week = plan.week_position(campaign)
    return {
        "slug": campaign.slug,
        "name": campaign.name,
        "week_index": week["week_index"],
        "week_count": week["week_count"],
        "systems": objective_rows(campaign),
        "active_window_minutes": ACTIVE_WINDOW_MINUTES,
        "active_pilots": active_pilots(campaign),
    }


# ---------------------------------------------------------------- systems


def objective_rows(campaign: Campaign) -> list[dict]:
    """One row per objective this week, highest priority first.

    Rows follow the week's targets, as the website's objectives table does.
    Before targets exist, each FW system gets one row from its own goal.
    """
    systems = {
        system.id: system for system in _systems_with_readings(campaign)
    }
    targets = CampaignWeekTarget.objects.filter(
        campaign_system_id__in=systems.keys(),
        week_start=campaign_week_start(),
        metric__in=METRIC_OBJECTIVES.keys(),
    ).values_list("campaign_system_id", "metric")
    pairs = [
        (systems[system_id], METRIC_OBJECTIVES[metric])
        for system_id, metric in targets
    ]
    if not pairs:
        pairs = [
            (system, _goal_objective(system.goal))
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
            )
            if snapshot_id
        ]
    )
    readings = CampaignAdvantageReading.objects.in_bulk(
        [
            system.day_ago_reading
            for system, objective in pairs
            if objective not in COMPLEX_OBJECTIVES and system.day_ago_reading
        ]
    )
    rows = [
        _row(system, objective, snapshots, readings)
        for system, objective in pairs
    ]
    return sorted(
        rows,
        key=lambda row: (PRIORITY_RANK.get(row["priority"], 1), row["name"]),
    )


def _systems_with_readings(campaign: Campaign):
    """Live systems, each with the ids of its latest and 24h-old snapshot
    and 24h-old advantage reading, in one query."""
    day_ago = timezone.now() - timedelta(hours=24)
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
        )
    )


def _goal_objective(goal: str) -> str:
    return (
        "capture_complexes" if goal in OFFENSIVE_GOALS else "defend_complexes"
    )


def _row(system, objective: str, snapshots: dict, readings: dict) -> dict:
    latest = snapshots.get(system.latest_snapshot)
    if objective in COMPLEX_OBJECTIVES:
        progress, change, detail = _complex_progress(
            objective, latest, snapshots.get(system.day_ago_snapshot)
        )
    else:
        progress, change, detail = _advantage_progress(
            objective,
            advantage.card_for(system),
            readings.get(system.day_ago_reading),
        )
    return {
        "system_id": system.id,
        "name": system.name,
        "solar_system_id": system.solar_system_id,
        "priority": system.priority,
        "holder": FACTIONS.get(latest.occupier_faction_id) if latest else None,
        "objective": objective,
        "objective_label": OBJECTIVE_LABELS[objective],
        "progress_percent": progress,
        "change_24h": change,
        "detail": detail,
    }


def _complex_progress(objective: str, latest, day_ago):
    """Victory points against the system's flip threshold.

    Capturing, the bar fills as our side's victory points climb. Defending,
    it is how far the attackers are from flipping it, so a quiet system is
    full and their victory points drain it.
    """
    if latest is None:
        return None, None, ""
    detail = (
        f"{latest.victory_points:,} of "
        f"{latest.victory_points_threshold:,} victory points"
        if latest.victory_points_threshold
        else ""
    )
    vp_percent = latest.contested_percent
    vp_change = (
        latest.contested_percent - day_ago.contested_percent
        if day_ago
        else None
    )
    if objective == "capture_complexes":
        return _round(vp_percent), _round(vp_change), detail
    return (
        _round(100 - vp_percent),
        _round(-vp_change) if vp_change is not None else None,
        detail,
    )


def _advantage_progress(objective: str, card: dict, day_ago):
    """Our advantage level, or for destroy, how far theirs has fallen."""
    destroy = objective == "destroy_advantage"
    level = card["enemy_pct" if destroy else "our_pct"]
    if level is None:
        return None, None, ""
    detail = f"{'Their' if destroy else 'Our'} advantage {level:.0f}%"
    was = (
        (day_ago.enemy_pct if destroy else day_ago.our_pct)
        if day_ago
        else None
    )
    change = level - was if was is not None else None
    if destroy:
        return (
            _round(100 - level),
            _round(-change) if change is not None else None,
            detail,
        )
    return _round(level), _round(change), detail


def _round(value):
    return round(value, 1) if value is not None else None


# ---------------------------------------------------------------- pilots


class _Activity:
    """What one pilot did in the window. Kills, losses and sites are sets of
    the things done, so two of a pilot's characters on one killmail still
    count as one kill."""

    def __init__(self, at, system, fallback):
        self.kills: set = set()
        self.losses: set = set()
        self.complexes: set = set()
        self.advantage_sites: set = set()
        self.in_fleet = False
        self.last_at = at
        self.system = system
        self.fallback = fallback  # (character_id, name) if no primary

    def note(self, at, system, field, key=None):
        if field == "in_fleet":
            self.in_fleet = True
        else:
            getattr(self, field).add(key)
        if at >= self.last_at:
            self.last_at, self.system = at, system


def active_pilots(campaign: Campaign) -> list[dict]:
    """Enlisted pilots who did something for the campaign in the last hour.

    A kill or loss in a campaign system, a site capture, or being seen in a
    campaign fleet all count. Each pilot shows as their primary character,
    most recent first.
    """
    since = timezone.now() - timedelta(minutes=ACTIVE_WINDOW_MINUTES)
    by_solar_system, by_campaign_system = {}, {}
    for system_id, solar_system_id, name in campaign.systems.values_list(
        "id", "solar_system_id", "name"
    ):
        by_campaign_system[system_id] = name
        by_solar_system[solar_system_id] = name
    pilots: dict[int, _Activity] = {}

    def note(user_id, at, system, field, key, fallback):
        activity = pilots.get(user_id)
        if activity is None:
            activity = pilots[user_id] = _Activity(at, system, fallback)
        activity.note(at, system, field, key)

    for (
        user_id,
        role,
        outcome,
        killmail_id,
        at,
        system_id,
        character_id,
        character_name,
    ) in CampaignKillmailParticipant.objects.filter(
        killmail__campaign=campaign,
        killmail__killmail_time__gte=since,
        enlisted=True,
        user__isnull=False,
    ).values_list(
        "user_id",
        "role",
        "killmail__outcome",
        "killmail_id",
        "killmail__killmail_time",
        "killmail__solar_system_id",
        "character_id",
        "character_name",
    ):
        if role == "victim":
            field = "losses"
        elif outcome != KillmailOutcome.LOSS:
            field = "kills"
        else:
            continue  # on the attacking side of our own loss
        note(
            user_id,
            at,
            by_solar_system.get(system_id),
            field,
            killmail_id,
            (character_id, character_name),
        )

    for (
        completion_id,
        user_id,
        kind,
        at,
        campaign_system_id,
        character_id,
    ) in CampaignSiteCompletion.objects.filter(
        campaign=campaign,
        occurred_at__gte=since,
        user__isnull=False,
        site_kind__in=(SiteKind.COMPLEX, *ADVANTAGE_SITE_KINDS),
    ).values_list(
        "id",
        "user_id",
        "site_kind",
        "occurred_at",
        "campaign_system_id",
        "character_id",
    ):
        note(
            user_id,
            at,
            by_campaign_system.get(campaign_system_id),
            "complexes" if kind == SiteKind.COMPLEX else "advantage_sites",
            completion_id,
            (character_id, ""),
        )

    _note_fleet_members(campaign, since, by_solar_system, note)
    return _as_rows(pilots)


def _note_fleet_members(campaign, since, by_solar_system, note) -> None:
    """Enlisted pilots seen in a campaign fleet. The fleet poller rewrites
    each member row every pass, so ``updated_at`` is when they were last
    seen in it.

    Member rows are never deleted, so fleets that ended before the window
    are ruled out first rather than walking every member they ever had.
    """
    enlisted = set(
        campaign.enlistments.filter(status="active").values_list(
            "user_id", flat=True
        )
    )
    members = list(
        EveFleetInstanceMember.objects.filter(
            Q(eve_fleet_instance__end_time__isnull=True)
            | Q(eve_fleet_instance__end_time__gte=since),
            eve_fleet_instance__eve_fleet__campaign=campaign,
            updated_at__gte=since,
        ).values_list(
            "character_id", "character_name", "updated_at", "solar_system_id"
        )
    )
    owners = dict(
        EveCharacter.objects.filter(
            character_id__in={member[0] for member in members}
        ).values_list("character_id", "user_id")
    )
    for character_id, character_name, at, system_id in members:
        user_id = owners.get(character_id)
        if user_id in enlisted:
            note(
                user_id,
                at,
                by_solar_system.get(system_id),
                "in_fleet",
                None,
                (character_id, character_name),
            )


def _as_rows(pilots: dict[int, _Activity]) -> list[dict]:
    """Each pilot as their primary character; without one, the character
    that did the thing stands in."""
    primaries = {
        user_id: (character_id, name)
        for user_id, character_id, name in EvePlayer.objects.filter(
            user_id__in=pilots.keys(), primary_character__isnull=False
        ).values_list(
            "user_id",
            "primary_character__character_id",
            "primary_character__character_name",
        )
    }
    fallback_names = dict(
        EveCharacter.objects.filter(
            character_id__in=[
                activity.fallback[0]
                for user_id, activity in pilots.items()
                if user_id not in primaries
            ]
        ).values_list("character_id", "character_name")
    )
    rows = []
    for user_id, activity in pilots.items():
        character_id, name = primaries.get(user_id, activity.fallback)
        if user_id not in primaries:
            name = fallback_names.get(character_id, name)
        if not character_id:
            continue
        rows.append(
            {
                "character_id": character_id,
                "character_name": name or "",
                "system": activity.system,
                "last_at": activity.last_at,
                "kills": len(activity.kills),
                "losses": len(activity.losses),
                "complexes": len(activity.complexes),
                "advantage_sites": len(activity.advantage_sites),
                "in_fleet": activity.in_fleet,
            }
        )
    return sorted(rows, key=lambda row: row["last_at"], reverse=True)
