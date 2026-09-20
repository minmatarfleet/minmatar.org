"""Shape ORM rows into API responses."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from campaigns.models import (
    Campaign,
    CampaignEnlistment,
    CampaignKillmail,
    CampaignKillmailParticipant,
    CampaignParticipantStat,
    CampaignSystem,
    CampaignSystemSnapshot,
    KillmailOutcome,
    SystemGoal,
)
from campaigns.services import advantage, snapshots, stats
from eveonline.models import EveCharacter, EvePlayer
from feed.models import FeedKillmail


def system_summary(
    campaign_system: CampaignSystem, with_trend: bool = True
) -> dict:
    """Contest, advantage and kills, each with its own direction of travel.

    A system card has to answer one question at a glance: are we gaining
    ground here or losing it.
    """
    now = timezone.now()
    latest = (
        CampaignSystemSnapshot.objects.filter(campaign_system=campaign_system)
        .order_by("-captured_at")
        .first()
    )
    day_ago = (
        CampaignSystemSnapshot.objects.filter(
            campaign_system=campaign_system,
            captured_at__lte=now - timedelta(hours=24),
        )
        .order_by("-captured_at")
        .first()
    )

    contested = latest.contested_percent if latest else None
    contested_change = (
        round(latest.contested_percent - day_ago.contested_percent, 2)
        if latest and day_ago
        else None
    )

    mails = CampaignKillmail.objects.filter(
        campaign=campaign_system.campaign,
        solar_system_id=campaign_system.solar_system_id,
    )
    kills_24h = mails.filter(
        outcome=KillmailOutcome.KILL,
        killmail_time__gte=now - timedelta(hours=24),
    ).count()
    losses_24h = mails.filter(
        outcome=KillmailOutcome.LOSS,
        killmail_time__gte=now - timedelta(hours=24),
    ).count()
    kills_prior = mails.filter(
        outcome=KillmailOutcome.KILL,
        killmail_time__gte=now - timedelta(hours=48),
        killmail_time__lt=now - timedelta(hours=24),
    ).count()

    advantage_state = advantage.state_for(campaign_system)

    return {
        "id": campaign_system.id,
        "name": campaign_system.name,
        "solar_system_id": campaign_system.solar_system_id,
        "role": campaign_system.role,
        "goal": campaign_system.goal,
        "contested_percent": (
            round(contested, 2) if contested is not None else None
        ),
        "contested_change_24h": contested_change,
        "victory_points": latest.victory_points if latest else None,
        "victory_points_threshold": (
            latest.victory_points_threshold if latest else None
        ),
        "operational_state": latest.operational_state if latest else "unknown",
        "owner_faction_id": latest.owner_faction_id if latest else None,
        "advantage_basis": advantage_state["basis"],
        "advantage_our_pct": advantage_state["our_pct"],
        "advantage_enemy_pct": advantage_state["enemy_pct"],
        "advantage_net_pct": advantage_state["net_pct"],
        "advantage_age_minutes": advantage_state["reading_age_minutes"],
        "advantage_is_stale": advantage_state["is_stale"],
        "kills_24h": kills_24h,
        "losses_24h": losses_24h,
        "kills_change_24h": kills_24h - kills_prior,
        "trend": snapshots.system_trend(campaign_system) if with_trend else [],
        "status_chip": _status_chip(
            campaign_system, contested_change, kills_24h, losses_24h
        ),
    }


def _status_chip(campaign_system, contested_change, kills, losses) -> str:
    """Gaining ground, holding or losing ground, read off the trends."""
    if contested_change is None:
        return "holding"

    wants_more_contest = campaign_system.goal == SystemGoal.CAPTURE
    moving_our_way = (
        contested_change > 0.5
        if wants_more_contest
        else contested_change < -0.5
    )
    moving_their_way = (
        contested_change < -0.5
        if wants_more_contest
        else contested_change > 0.5
    )

    if moving_our_way and kills >= losses:
        return "gaining"
    if moving_their_way and losses > kills:
        return "losing"
    if moving_our_way:
        return "gaining"
    if moving_their_way:
        return "losing"
    return "holding"


def campaign_systems(
    campaign: Campaign, with_trend: bool = True
) -> list[dict]:
    rows = [
        system_summary(system, with_trend=with_trend)
        for system in campaign.systems.filter(retired_at__isnull=True)
    ]
    # Most contested first: that is where the fight is.
    return sorted(
        rows, key=lambda row: row["contested_percent"] or 0, reverse=True
    )


def list_item(campaign: Campaign, user=None) -> dict:
    totals = stats.campaign_totals(campaign)
    return {
        "id": campaign.id,
        "slug": campaign.slug,
        "name": campaign.name,
        "short_code": campaign.short_code,
        "tagline": campaign.tagline,
        "status": campaign.status,
        "start_at": campaign.start_at,
        "end_at": campaign.end_at,
        "cover_image_url": campaign.cover_image_url,
        "systems": campaign_systems(campaign, with_trend=False),
        "enlisted": totals["enlisted"],
        "kills": totals["kills"],
        "isk_destroyed": totals["isk_destroyed"],
        "is_enlisted": is_enlisted(campaign, user),
    }


def is_enlisted(campaign: Campaign, user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return campaign.enlistments.filter(user=user, status="active").exists()


def killmail_out(mail: CampaignKillmail) -> dict:
    return {
        "killmail_id": mail.killmail_id,
        "killmail_time": mail.killmail_time,
        "outcome": mail.outcome,
        "solar_system_id": mail.solar_system_id,
        "victim_character_name": mail.victim_character_name or "",
        "victim_ship_type_id": mail.victim_ship_type_id,
        "isk_value": mail.isk_value,
        "enlisted_attacker_count": mail.enlisted_attacker_count,
        "is_solo": mail.is_solo,
    }


def coverage_window(campaign: Campaign, days: int = 7):
    """The last ``days`` of fighting, not the last ``days`` of wall clock.

    A campaign that finished last month, or one whose feed has been quiet
    for a week, would otherwise render an empty chart. The window ends at
    the most recent thing that happened in the campaign.
    """
    latest = (
        CampaignKillmail.objects.filter(campaign=campaign)
        .order_by("-killmail_time")
        .values_list("killmail_time", flat=True)
        .first()
    )
    anchor = min(latest or timezone.now(), timezone.now())
    anchor = max(anchor, campaign.start_at)
    return anchor - timedelta(days=days), anchor


def coverage_by_hour(campaign: Campaign, days: int = 7) -> list[dict]:
    """Enlisted activity per UTC hour against hostile activity per hour.

    The hole where they play and we do not is the point of this chart.
    """
    since, until = coverage_window(campaign, days)

    ours = CampaignKillmailParticipant.objects.filter(
        killmail__campaign=campaign,
        killmail__killmail_time__gte=since,
        killmail__killmail_time__lte=until,
        enlisted=True,
    ).values_list("killmail__killmail_time", flat=True)
    our_hours: dict[int, set] = {hour: set() for hour in range(24)}
    for moment in ours:
        our_hours[moment.hour].add(moment.date())

    hostile_counts = {hour: 0 for hour in range(24)}
    hostile = FeedKillmail.objects.filter(
        solar_system_id__in=campaign.system_ids(),
        killmail_time__gte=since,
        killmail_time__lte=until,
    ).values_list("killmail_time", flat=True)
    for moment in hostile:
        hostile_counts[moment.hour] += 1

    return [
        {
            "hour": hour,
            "our_active_days": len(our_hours[hour]),
            "hostile_activity": hostile_counts[hour],
        }
        for hour in range(24)
    ]


def roster_rows(campaign: Campaign) -> list[dict]:
    """The roster, in a handful of queries rather than three per pilot."""
    enlistments = list(
        CampaignEnlistment.objects.filter(campaign=campaign, status="active")
        .select_related("user")
        .annotate(
            included=Count(
                "characters", filter=Q(characters__included_until__isnull=True)
            )
        )
    )
    if not enlistments:
        return []

    user_ids = [enlistment.user_id for enlistment in enlistments]

    players = {
        player.user_id: player
        for player in EvePlayer.objects.filter(
            user_id__in=user_ids
        ).select_related("primary_character")
    }
    stats_by_user = {
        row.user_id: row
        for row in CampaignParticipantStat.objects.filter(campaign=campaign)
    }
    tracked_by_user = dict(
        EveCharacter.objects.filter(
            user_id__in=user_ids,
            token__scopes__name="esi-characters.read_notifications.v1",
        )
        .values_list("user_id")
        .annotate(n=Count("id", distinct=True))
        .values_list("user_id", "n")
    )

    rows = []
    for enlistment in enlistments:
        player = players.get(enlistment.user_id)
        primary = player.primary_character if player else None
        stat = stats_by_user.get(enlistment.user_id)

        rows.append(
            {
                "user_id": enlistment.user_id,
                "username": enlistment.user.username,
                "primary_character": (
                    primary.character_name if primary else ""
                ),
                "corporation_id": primary.corporation_id if primary else None,
                "prime_time": (player.prime_time if player else "") or "",
                "observed_prime_time": (
                    stat.observed_prime_time if stat else ""
                ),
                "last_active_day": stat.last_active_day if stat else None,
                "streak_days": stat.streak_days if stat else 0,
                "points": stat.points if stat else 0,
                "characters_included": enlistment.included,
                "characters_tracked": tracked_by_user.get(
                    enlistment.user_id, 0
                ),
            }
        )

    return sorted(rows, key=lambda row: row["points"], reverse=True)
