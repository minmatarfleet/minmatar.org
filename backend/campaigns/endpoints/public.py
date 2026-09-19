"""Read endpoints. Everything a campaign page renders comes from here."""

from __future__ import annotations

from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone

from app.errors import ErrorResponse
from authentication import AuthOptional
from campaigns.endpoints.base import router
from campaigns.endpoints import schemas, serializers
from campaigns.helpers import campaign_week_start
from campaigns.models import (
    Campaign,
    CampaignAward,
    CampaignEvent,
    CampaignKillmail,
    CampaignParticipantStat,
    CampaignSiteCompletion,
    CampaignStatus,
    CampaignWeekTarget,
)
from campaigns.services import plan, stats
from groups.helpers.feature_access import require_feature

VIEW_FEATURE = "campaigns.view"
MAX_LIMIT = 200
HOSTILE_GANG_WINDOW_HOURS = 2


def _visible(request):
    """Campaigns a viewer may see. Drafts are for their creator and staff."""
    queryset = Campaign.objects.exclude(status=CampaignStatus.DRAFT)
    user = request.user
    if getattr(user, "is_authenticated", False) and (
        user.is_staff or user.is_superuser
    ):
        queryset = Campaign.objects.all()
    return queryset.prefetch_related("systems")


def _get(request, slug: str) -> Campaign:
    return get_object_or_404(_visible(request), slug=slug)


def _may_read(request, campaign: Campaign):
    """Gate every read on the campaign's own visibility.

    A campaign's sub-resources are as sensitive as the campaign itself: the
    roster names pilots, the coverage chart shows the hours the alliance is
    not online, and the strip says which gang is forming right now. Only a
    campaign explicitly marked public is readable without the feature.
    """
    if campaign.visibility == "public":
        return None
    return require_feature(request.user, VIEW_FEATURE)


def _clamp(limit: int) -> int:
    """A page size the database can actually serve."""
    return max(1, min(limit, MAX_LIMIT))


@router.get(
    "",
    response={200: list[schemas.CampaignListItem], 403: ErrorResponse},
    auth=AuthOptional(),
)
def list_campaigns(request, status: str = ""):
    """Live campaigns first, then upcoming, then finished.

    A viewer without the feature still sees campaigns marked public, and
    nothing else.
    """
    permitted = require_feature(request.user, VIEW_FEATURE) is None
    queryset = _visible(request)
    if not permitted:
        queryset = queryset.filter(visibility="public")
        if not queryset.exists():
            return require_feature(request.user, VIEW_FEATURE)
    if status:
        queryset = queryset.filter(status=status)

    order = {
        CampaignStatus.ACTIVE: 0,
        CampaignStatus.SCHEDULED: 1,
        CampaignStatus.COMPLETED: 2,
        CampaignStatus.ARCHIVED: 3,
        CampaignStatus.DRAFT: 4,
    }
    campaigns = sorted(
        queryset,
        key=lambda c: (order.get(c.status, 9), -c.start_at.timestamp()),
    )
    user = (
        request.user
        if getattr(request.user, "is_authenticated", False)
        else None
    )
    return [serializers.list_item(campaign, user) for campaign in campaigns]


@router.get(
    "/{slug}",
    response={200: schemas.CampaignDetail, 403: ErrorResponse, 404: None},
    auth=AuthOptional(),
)
def get_campaign(request, slug: str):
    campaign = _get(request, slug)
    denied = _may_read(request, campaign)
    if denied:
        return denied

    user = (
        request.user
        if getattr(request.user, "is_authenticated", False)
        else None
    )

    my_stat = (
        CampaignParticipantStat.objects.filter(
            campaign=campaign, user=user
        ).first()
        if user
        else None
    )
    standing = getattr(campaign, "standing_fleet", None)
    enlistment = (
        campaign.enlistments.filter(user=user, status="active").first()
        if user
        else None
    )

    return {
        "id": campaign.id,
        "slug": campaign.slug,
        "name": campaign.name,
        "short_code": campaign.short_code,
        "tagline": campaign.tagline,
        "description_md": campaign.description_md,
        "cover_image_url": campaign.cover_image_url,
        "status": campaign.status,
        "start_at": campaign.start_at,
        "end_at": campaign.end_at,
        "commander_order_text": campaign.commander_order_text,
        "commander_order_is_draft": campaign.commander_order_is_draft,
        "systems": serializers.campaign_systems(campaign),
        "totals": stats.campaign_totals(campaign),
        "is_enlisted": enlistment is not None,
        "my_points": my_stat.points if my_stat else 0,
        "my_rank": my_stat.rank_points if my_stat else None,
        "my_streak": my_stat.streak_days if my_stat else 0,
        "characters_included": (
            enlistment.characters.filter(included_until__isnull=True).count()
            if enlistment
            else 0
        ),
        "characters_tracked": my_stat.characters_tracked if my_stat else 0,
        "standing_fleet_up": bool(standing and standing.is_up),
        "standing_fleet_members": standing.member_count if standing else 0,
        "standing_fleet_boss": (
            str(standing.current_boss_character_id)
            if standing and standing.current_boss_character_id
            else None
        ),
    }


@router.get(
    "/{slug}/now",
    response={200: schemas.RightNow, 403: ErrorResponse, 404: None},
    auth=AuthOptional(),
)
def get_right_now(request, slug: str):
    """Why undock in the next ten minutes."""
    campaign = _get(request, slug)
    denied = _may_read(request, campaign)
    if denied:
        return denied
    user = (
        request.user
        if getattr(request.user, "is_authenticated", False)
        else None
    )

    # "Right now" means right now: an event the feed still calls active but
    # that started hours ago is history, not a reason to undock.
    live_since = timezone.now() - timedelta(hours=HOSTILE_GANG_WINDOW_HOURS)
    hostile = (
        CampaignEvent.objects.filter(
            campaign=campaign,
            kind=CampaignEvent.Kind.HOSTILE_GANG,
            is_active=True,
            occurred_at__gte=live_since,
        )
        .select_related("campaign_system")
        .order_by("-occurred_at")[:3]
    )

    # A gang is only worth joining while it is still forming up.
    forming_since = timezone.now() - timedelta(hours=2)
    forming = (
        CampaignEvent.objects.filter(
            campaign=campaign,
            kind=CampaignEvent.Kind.GANG_FORMED,
            is_active=True,
            occurred_at__gte=forming_since,
        )
        .select_related("campaign_system", "user")
        .order_by("-occurred_at")[:5]
    )

    standing = getattr(campaign, "standing_fleet", None)
    my_stat = (
        CampaignParticipantStat.objects.filter(
            campaign=campaign, user=user
        ).first()
        if user
        else None
    )

    orders = plan.orders_for(campaign, user) if user else []

    ticker = [
        {
            "killmail_id": mail.killmail_id,
            "outcome": mail.outcome,
            "isk_value": mail.isk_value,
            "killmail_time": mail.killmail_time.isoformat(),
        }
        for mail in CampaignKillmail.objects.filter(campaign=campaign)[:8]
    ]

    return {
        "active_pilots": stats.active_recently(campaign),
        "system_heat": stats.system_heat(campaign),
        "hostile_gangs": [
            {
                "title": event.title,
                "system": (
                    event.campaign_system.name if event.campaign_system else ""
                ),
                "occurred_at": event.occurred_at.isoformat(),
            }
            for event in hostile
        ],
        "standing_fleet_up": bool(standing and standing.is_up),
        "standing_fleet_members": standing.member_count if standing else 0,
        "standing_fleet_boss": (
            str(standing.current_boss_character_id)
            if standing and standing.current_boss_character_id
            else None
        ),
        "gangs_forming": [
            {
                "id": event.id,
                "ships": (event.payload or {}).get("ships", ""),
                "note": event.body,
                "system": (
                    event.campaign_system.name
                    if event.campaign_system
                    else None
                ),
                "started_by": (event.user.username if event.user else ""),
                "occurred_at": event.occurred_at.isoformat(),
            }
            for event in forming
        ],
        "my_streak": my_stat.streak_days if my_stat else 0,
        "my_orders_done": sum(1 for order in orders if order["completed"]),
        "my_orders_total": len(orders),
        "ticker": ticker,
    }


@router.get(
    "/{slug}/week",
    response={200: schemas.WeekPlan, 403: ErrorResponse, 404: None},
    auth=AuthOptional(),
)
def get_week(request, slug: str):
    campaign = _get(request, slug)
    denied = _may_read(request, campaign)
    if denied:
        return denied
    week_start = campaign_week_start()

    targets = [
        {
            "id": row.id,
            "system": row.campaign_system.name,
            "system_id": row.campaign_system_id,
            "goal": row.campaign_system.goal,
            "metric": row.metric,
            "target": row.target,
            "progress": row.progress,
            "pace_expected": row.pace_expected,
            "pace": row.pace,
            "proposed": row.proposed,
            "last_week_actual": row.last_week_actual,
            "days_under_line": row.days_under_line,
            "projected_arc_date": row.projected_arc_date,
        }
        for row in CampaignWeekTarget.objects.filter(
            campaign_system__campaign=campaign, week_start=week_start
        ).select_related("campaign_system")
    ]

    return {
        "week_start": week_start,
        "targets": targets,
        "commander_order_text": campaign.commander_order_text,
        "summary": stats.week_summary(campaign),
    }


@router.get(
    "/{slug}/orders",
    response={200: list[schemas.OrderOut], 403: ErrorResponse, 404: None},
    auth=AuthOptional(),
)
def get_orders(request, slug: str):
    campaign = _get(request, slug)
    denied = _may_read(request, campaign)
    if denied:
        return denied
    user = (
        request.user
        if getattr(request.user, "is_authenticated", False)
        else None
    )
    return plan.orders_for(campaign, user)


@router.get(
    "/{slug}/systems",
    response={
        200: list[schemas.CampaignSystemSummary],
        403: ErrorResponse,
        404: None,
    },
    auth=AuthOptional(),
)
def get_systems(request, slug: str):
    campaign = _get(request, slug)
    denied = _may_read(request, campaign)
    if denied:
        return denied
    return serializers.campaign_systems(campaign)


@router.get(
    "/{slug}/leaderboard",
    response={
        200: list[schemas.LeaderboardRow],
        403: ErrorResponse,
        404: None,
    },
    auth=AuthOptional(),
)
def get_leaderboard(
    request,
    slug: str,
    metric: str = "points",
    period: str = "week",
    limit: int = 25,
):
    campaign = _get(request, slug)
    denied = _may_read(request, campaign)
    if denied:
        return denied
    return stats.leaderboard(
        campaign, metric=metric, period=period, limit=_clamp(limit)
    )


@router.get(
    "/{slug}/killmails",
    response={200: list[schemas.KillmailOut], 403: ErrorResponse, 404: None},
    auth=AuthOptional(),
)
def get_killmails(request, slug: str, outcome: str = "", limit: int = 50):
    campaign = _get(request, slug)
    denied = _may_read(request, campaign)
    if denied:
        return denied
    queryset = CampaignKillmail.objects.filter(campaign=campaign).exclude(
        outcome="unscored"
    )
    if outcome:
        queryset = queryset.filter(outcome=outcome)
    return [
        serializers.killmail_out(mail) for mail in queryset[: _clamp(limit)]
    ]


@router.get(
    "/{slug}/sites",
    response={200: list[schemas.SiteOut], 403: ErrorResponse, 404: None},
    auth=AuthOptional(),
)
def get_sites(request, slug: str, limit: int = 50):
    campaign = _get(request, slug)
    denied = _may_read(request, campaign)
    if denied:
        return denied

    rows = CampaignSiteCompletion.objects.filter(
        campaign=campaign
    ).select_related("campaign_system", "user", "complex")[: _clamp(limit)]
    return [
        {
            "id": row.id,
            "occurred_at": row.occurred_at,
            "site_kind": row.site_kind,
            "amount_lp": row.amount_lp,
            "system": row.campaign_system.name,
            "username": row.user.username if row.user else None,
            "plex_class": (
                row.complex.inferred_plex_class if row.complex else ""
            ),
            "confidence": row.complex.confidence if row.complex else "",
        }
        for row in rows
    ]


@router.get(
    "/{slug}/timeline",
    response={200: list[schemas.TimelineEvent], 403: ErrorResponse, 404: None},
    auth=AuthOptional(),
)
def get_timeline(request, slug: str, limit: int = 50):
    campaign = _get(request, slug)
    denied = _may_read(request, campaign)
    if denied:
        return denied

    rows = CampaignEvent.objects.filter(campaign=campaign).select_related(
        "campaign_system"
    )[: _clamp(limit)]
    return [
        {
            "id": event.id,
            "kind": event.kind,
            "occurred_at": event.occurred_at,
            "title": event.title,
            "body": event.body,
            "side": event.side,
            "source": event.source,
            "system": (
                event.campaign_system.name if event.campaign_system else None
            ),
            "is_active": event.is_active,
        }
        for event in rows
    ]


@router.get(
    "/{slug}/awards",
    response={200: list[schemas.AwardOut], 403: ErrorResponse, 404: None},
    auth=AuthOptional(),
)
def get_awards(request, slug: str, limit: int = 50):
    """Weekly winners newest first, then the campaign awards."""
    campaign = _get(request, slug)
    denied = _may_read(request, campaign)
    if denied:
        return denied

    rows = CampaignAward.objects.filter(campaign=campaign).select_related(
        "user"
    )[: _clamp(limit)]
    return [
        {
            "code": award.code,
            "label": award.label,
            "scope": award.scope,
            "week_start": award.week_start,
            "awarded_at": award.awarded_at,
            "username": award.user.username,
            "value": (award.payload or {}).get("value"),
            "metric": (award.payload or {}).get("metric", ""),
        }
        for award in rows
    ]


@router.get(
    "/{slug}/roster",
    response={200: schemas.Roster, 403: ErrorResponse, 404: None},
    auth=AuthOptional(),
)
def get_roster(request, slug: str):
    """Who is in, when they play, and where the coverage hole is."""
    campaign = _get(request, slug)
    denied = _may_read(request, campaign)
    if denied:
        return denied

    rows = serializers.roster_rows(campaign)

    by_prime_time: dict[str, int] = {}
    for row in rows:
        label = row["prime_time"] or row["observed_prime_time"] or "Unknown"
        by_prime_time[label] = by_prime_time.get(label, 0) + 1

    return {
        "pilots": rows,
        "coverage": serializers.coverage_by_hour(campaign),
        "by_prime_time": by_prime_time,
    }
