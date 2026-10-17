"""The desktop app's Campaigns window: where each system stands, who is out.

The window is glanced at over the game, so it carries one progress figure
per objective and its move, never the contest breakdown. The rows are the
ones the website's objectives table draws (campaigns/services/objectives.py),
rounded to a tenth and in the shape released desktop versions read.

Every desktop app polls this once a minute, so it is built from a handful
of queries and served from the cache: one build per campaign per minute,
whoever asks.
"""

from __future__ import annotations

import time
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from campaigns.models import (
    ADVANTAGE_SITE_KINDS,
    Campaign,
    CampaignKillmailParticipant,
    CampaignSiteCompletion,
    CampaignStatus,
    KillmailOutcome,
    SiteKind,
)
from campaigns.services import objectives, plan
from eveonline.helpers.corporations.safe_cache import (
    cache_add,
    cache_delete,
    cache_get,
    cache_set,
)
from eveonline.models import EveCharacter, EvePlayer
from fleets.models import EveFleetInstanceMember

ACTIVE_WINDOW_MINUTES = 60
FRESH_SECONDS = 60
# A stale copy is served while one request rebuilds it, so a minute's worth
# of desktop apps never all rebuild at once when the fresh copy lapses.
STALE_SECONDS = 10 * 60
REBUILD_LOCK_SECONDS = 30
CACHE_KEY = "campaigns:overlay:{campaign_id}"
LOCK_KEY = "campaigns:overlay:{campaign_id}:rebuilding"

OBJECTIVE_LABELS = {
    "capture_complexes": "Capture complexes",
    "defend_complexes": "Defend complexes",
    "gain_advantage": "Gain advantage",
    "hold_advantage": "Hold advantage",
    "destroy_advantage": "Destroy advantage",
}


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
    """The week's objective rows (campaigns/services/objectives.py), in the
    shape installed desktop versions read. Structure objectives have no
    place in the window."""
    return [
        _overlay_row(row)
        for row in objectives.weekly_rows(campaign)
        if row["objective"] in OBJECTIVE_LABELS
    ]


def _overlay_row(row: dict) -> dict:
    return {
        "system_id": row["system_id"],
        "name": row["name"],
        "solar_system_id": row["solar_system_id"],
        "priority": row["priority"],
        "holder": row["holder"],
        "objective": row["objective"],
        "objective_label": OBJECTIVE_LABELS[row["objective"]],
        "progress_percent": _round(row["progress_percent"]),
        "change_week": _round(row["change_week"]),
        "change_24h": _round(row["change_24h"]),
        "flipped": row["flipped"],
        "detail": _detail(row),
    }


def _detail(row: dict) -> str:
    """The figure behind the bar: victory points, or the advantage level."""
    if row["objective"] in objectives.COMPLEX_OBJECTIVES:
        if (
            row["progress_percent"] is None
            or not row["victory_points_threshold"]
        ):
            return ""
        return (
            f"{row['victory_points']:,} of "
            f"{row['victory_points_threshold']:,} victory points"
        )
    if row["advantage_level"] is None:
        return ""
    whose = "Their" if row["objective"] == "destroy_advantage" else "Our"
    return f"{whose} advantage {row['advantage_level']:.0f}%"


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
