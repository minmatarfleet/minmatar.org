"""The desktop app's Campaigns window: where each system stands, who is out.

The window is glanced at over the game, so it carries one progress figure
per objective and the 24h move, never the contest breakdown. Complex
objectives are measured in victory points; advantage objectives in the
advantage level. Every progress figure reads "higher is better", so a
defensive or destroy objective is inverted before it gets here.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from campaigns.endpoints import serializers
from campaigns.helpers import campaign_week_start
from campaigns.models import (
    Campaign,
    CampaignAdvantageReading,
    CampaignKillmailParticipant,
    CampaignSiteCompletion,
    CampaignStatus,
    CampaignWeekTarget,
    SiteKind,
    SystemGoal,
)
from campaigns.services import plan
from eveonline.helpers.corporations.safe_cache import cache_get, cache_set
from eveonline.models import EveCharacter, EvePlayer
from fleets.models import EveFleetInstanceMember

ACTIVE_WINDOW_MINUTES = 60
CACHE_SECONDS = 60
CACHE_KEY = "campaigns:overlay:{campaign_id}"

FACTIONS = {500002: "minmatar", 500003: "amarr"}
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
OFFENSIVE_GOALS = (SystemGoal.TAKE, SystemGoal.PRESSURE, SystemGoal.DISRUPT)
ADVANTAGE_SITE_KINDS = (
    SiteKind.ADVANTAGE_SITE,
    SiteKind.RENDEZVOUS_POINT,
    SiteKind.PROPAGANDA_BEACON,
    SiteKind.LISTENING_OUTPOST,
    SiteKind.SUPPLY_CACHE,
    SiteKind.BATTLEFIELD,
)


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
    cached = cache_get(key)
    if cached is not None:
        return cached
    week = plan.week_position(campaign)
    payload = {
        "slug": campaign.slug,
        "name": campaign.name,
        "week_index": week["week_index"],
        "week_count": week["week_count"],
        "systems": objective_rows(campaign),
        "active_window_minutes": ACTIVE_WINDOW_MINUTES,
        "active_pilots": active_pilots(campaign),
    }
    cache_set(key, payload, CACHE_SECONDS)
    return payload


# ---------------------------------------------------------------- systems


def objective_rows(campaign: Campaign) -> list[dict]:
    """One row per objective this week, highest priority first.

    Rows follow the week's targets, as the website's objectives table does.
    Before targets exist, each FW system gets one row from its own goal.
    """
    systems = {
        system.id: system
        for system in campaign.systems.filter(
            retired_at__isnull=True
        ).select_related("advantage_state")
    }
    summaries = {
        system_id: serializers.system_summary(system, with_trend=False)
        for system_id, system in systems.items()
    }
    targets = CampaignWeekTarget.objects.filter(
        campaign_system_id__in=systems.keys(),
        week_start=campaign_week_start(),
        metric__in=METRIC_OBJECTIVES.keys(),
    )
    pairs = [
        (systems[target.campaign_system_id], METRIC_OBJECTIVES[target.metric])
        for target in targets
    ]
    if not pairs:
        pairs = [
            (system, _goal_objective(system.goal))
            for system in systems.values()
            if system.is_fw_objective
        ]

    rows = [
        _row(system, objective, summaries[system.id])
        for system, objective in pairs
    ]
    return sorted(
        rows,
        key=lambda row: (PRIORITY_RANK.get(row["priority"], 1), row["name"]),
    )


def _goal_objective(goal: str) -> str:
    return (
        "capture_complexes" if goal in OFFENSIVE_GOALS else "defend_complexes"
    )


def _row(system, objective: str, summary: dict) -> dict:
    if objective in ("capture_complexes", "defend_complexes"):
        progress, change, detail = _complex_progress(objective, summary)
    else:
        progress, change, detail = _advantage_progress(
            system, objective, summary
        )
    return {
        "system_id": system.id,
        "name": system.name,
        "solar_system_id": system.solar_system_id,
        "priority": system.priority,
        "holder": FACTIONS.get(summary["occupier_faction_id"]),
        "objective": objective,
        "objective_label": OBJECTIVE_LABELS[objective],
        "progress_percent": progress,
        "change_24h": change,
        "detail": detail,
    }


def _complex_progress(objective: str, summary: dict):
    """Victory points against the system's flip threshold.

    Capturing, the bar fills as our side's victory points climb. Defending,
    it is how far the attackers are from flipping it, so a quiet system is
    full and their victory points drain it.
    """
    vp_percent = summary["contested_percent"]
    vp_change = summary["contested_change_24h"]
    vp = summary["victory_points"]
    threshold = summary["victory_points_threshold"]
    detail = f"{vp:,} of {threshold:,} victory points" if threshold else ""
    if vp_percent is None:
        return None, None, detail
    if objective == "capture_complexes":
        return _round(vp_percent), _round(vp_change), detail
    return (
        _round(100 - vp_percent),
        _round(-vp_change) if vp_change is not None else None,
        detail,
    )


def _advantage_progress(system, objective: str, summary: dict):
    """Our advantage level, or for destroy, how far theirs has fallen."""
    destroy = objective == "destroy_advantage"
    level = summary["advantage_enemy_pct" if destroy else "advantage_our_pct"]
    if level is None:
        return None, None, ""
    detail = f"{'Their' if destroy else 'Our'} advantage {level:.0f}%"
    day_ago = (
        CampaignAdvantageReading.objects.filter(
            campaign_system=system,
            status="accepted",
            reported_at__lte=timezone.now() - timedelta(hours=24),
        )
        .order_by("-reported_at")
        .first()
    )
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


def active_pilots(campaign: Campaign) -> list[dict]:
    """Enlisted pilots who did something for the campaign in the last hour.

    A kill or loss in a campaign system, a site capture, or being seen in a
    campaign fleet all count. Each pilot shows as their primary character,
    most recent first.
    """
    since = timezone.now() - timedelta(minutes=ACTIVE_WINDOW_MINUTES)
    by_solar_system = dict(
        campaign.systems.values_list("solar_system_id", "name")
    )
    by_campaign_system = dict(campaign.systems.values_list("id", "name"))
    pilots: dict[int, dict] = {}

    def note(user_id, at, system, field, fallback):
        row = pilots.setdefault(
            user_id,
            {
                "kills": 0,
                "losses": 0,
                "complexes": 0,
                "advantage_sites": 0,
                "in_fleet": False,
                "last_at": at,
                "system": system,
                "fallback": fallback,
            },
        )
        if field == "in_fleet":
            row["in_fleet"] = True
        else:
            row[field] += 1
        if at >= row["last_at"]:
            row["last_at"], row["system"] = at, system

    for (
        user_id,
        role,
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
        "killmail__killmail_time",
        "killmail__solar_system_id",
        "character_id",
        "character_name",
    ):
        note(
            user_id,
            at,
            by_solar_system.get(system_id),
            "kills" if role == "attacker" else "losses",
            (character_id, character_name),
        )

    for (
        user_id,
        kind,
        at,
        campaign_system_id,
        character_id,
    ) in CampaignSiteCompletion.objects.filter(
        campaign=campaign, occurred_at__gte=since, user__isnull=False
    ).values_list(
        "user_id",
        "site_kind",
        "occurred_at",
        "campaign_system_id",
        "character_id",
    ):
        if kind == SiteKind.COMPLEX:
            field = "complexes"
        elif kind in ADVANTAGE_SITE_KINDS:
            field = "advantage_sites"
        else:
            continue
        note(
            user_id,
            at,
            by_campaign_system.get(campaign_system_id),
            field,
            (character_id, ""),
        )

    _note_fleet_members(campaign, since, by_solar_system, note)

    players = {
        player.user_id: player.primary_character
        for player in EvePlayer.objects.filter(
            user_id__in=pilots.keys()
        ).select_related("primary_character")
    }
    # Without a primary character, the character that did the thing stands in.
    fallback_names = dict(
        EveCharacter.objects.filter(
            character_id__in=[
                row["fallback"][0]
                for user_id, row in pilots.items()
                if not players.get(user_id)
            ]
        ).values_list("character_id", "character_name")
    )
    rows = []
    for user_id, row in pilots.items():
        primary = players.get(user_id)
        if primary:
            character_id = primary.character_id
            character_name = primary.character_name
        else:
            character_id, character_name = row["fallback"]
            character_name = fallback_names.get(character_id, character_name)
        if not character_id:
            continue
        rows.append(
            {
                "character_id": character_id,
                "character_name": character_name or "",
                "system": row["system"],
                "last_at": row["last_at"],
                "kills": row["kills"],
                "losses": row["losses"],
                "complexes": row["complexes"],
                "advantage_sites": row["advantage_sites"],
                "in_fleet": row["in_fleet"],
            }
        )
    return sorted(rows, key=lambda row: row["last_at"], reverse=True)


def _note_fleet_members(campaign, since, by_solar_system, note) -> None:
    """Enlisted pilots seen in a campaign fleet. The fleet poller rewrites
    each member row every pass, so ``updated_at`` is when they were last
    seen in it."""
    enlisted = set(
        campaign.enlistments.filter(status="active").values_list(
            "user_id", flat=True
        )
    )
    members = list(
        EveFleetInstanceMember.objects.filter(
            eve_fleet_instance__eve_fleet__campaign=campaign,
            updated_at__gte=since,
        ).values_list(
            "character_id", "character_name", "updated_at", "solar_system_id"
        )
    )
    owners = dict(
        EveCharacter.objects.filter(
            character_id__in=[member[0] for member in members]
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
                (character_id, character_name),
            )
