"""Small shared helpers: campaign days, weeks and character/user resolution."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from datetime import timezone as datetime_timezone

from django.db.models import Q
from django.utils import timezone

from app.errors import ErrorResponse
from campaigns.models import (
    DAY_BOUNDARY_HOUR,
    Campaign,
    CampaignEnlistmentCharacter,
    CampaignEnlistmentPeriod,
    CampaignStatus,
    CampaignSystemArc,
    SystemGoal,
)
from feed.models import FeedMonitoredSystem


def campaign_day(moment: datetime | None = None) -> date:
    """The campaign day a moment falls in. Days roll over at 11:00 UTC."""
    moment = moment or timezone.now()
    moment = moment.astimezone(datetime_timezone.utc)
    if moment.hour < DAY_BOUNDARY_HOUR:
        return (moment - timedelta(days=1)).date()
    return moment.date()


def week_start_for(day: date) -> date:
    """The Thursday that opened the campaign week containing ``day``."""
    # Monday is 0, Thursday is 3.
    return day - timedelta(days=(day.weekday() - 3) % 7)


def campaign_week_start(moment: datetime | None = None) -> date:
    """The Thursday that opened the campaign week containing ``moment``."""
    return week_start_for(campaign_day(moment))


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """UTC datetimes that open and close a campaign day."""
    start = datetime(
        day.year,
        day.month,
        day.day,
        DAY_BOUNDARY_HOUR,
        tzinfo=datetime_timezone.utc,
    )
    return start, start + timedelta(days=1)


def week_bounds(week_start: date) -> tuple[datetime, datetime]:
    start, _ = day_bounds(week_start)
    return start, start + timedelta(days=7)


def counting_campaigns(solar_system_id: int, moment: datetime):
    """Campaigns that should count activity in a system at a moment.

    Scheduled campaigns count too: a campaign is created before it starts so
    the ingest hook is already live, and the plan forbids backfilling.

    A campaign matches when the system is listed as an FW objective, or when
    a structure under recon sits in that system (ops theaters alone do not
    score ship kills; citadel grids still match via structures).
    """
    return Campaign.objects.filter(
        Q(
            systems__solar_system_id=solar_system_id,
            systems__retired_at__isnull=True,
            systems__is_fw_objective=True,
        )
        | Q(structures__solar_system_id=solar_system_id),
        status__in=["scheduled", "active"],
        start_at__lte=moment,
        end_at__gte=moment,
    ).distinct()


class CampaignRoster:
    """Who counts for a campaign, loaded once and answered in memory.

    Attribution runs per killmail, so asking the database which characters
    were included at that instant would be one query per mail. The roster is
    small, so we load it once and evaluate the inclusion and enlistment
    periods in Python.
    """

    def __init__(self, campaign: Campaign):
        self.campaign = campaign
        self._characters: dict[int, list[tuple]] = {}
        self._periods: dict[int, list[tuple]] = {}
        self._load()

    def _load(self):
        rows = CampaignEnlistmentCharacter.objects.filter(
            enlistment__campaign=self.campaign,
            enlistment__status="active",
        ).select_related("character", "enlistment__user")

        for row in rows:
            self._characters.setdefault(row.character.character_id, []).append(
                (
                    row.included_from,
                    row.included_until,
                    row.enlistment_id,
                    row.enlistment.user,
                )
            )

        for (
            enlistment_id,
            enlisted_at,
            left_at,
        ) in CampaignEnlistmentPeriod.objects.filter(
            enlistment__campaign=self.campaign,
            enlistment__status="active",
        ).values_list(
            "enlistment_id", "enlisted_at", "left_at"
        ):
            self._periods.setdefault(enlistment_id, []).append(
                (enlisted_at, left_at)
            )

    def user_for(self, character_id: int, moment: datetime):
        """The pilot this character counted for at that moment, or None."""
        for (
            included_from,
            included_until,
            enlistment_id,
            user,
        ) in self._characters.get(character_id, []):
            if moment < included_from:
                continue
            if included_until is not None and moment >= included_until:
                continue
            for opened_at, closed_at in self._periods.get(enlistment_id, []):
                if opened_at <= moment and (
                    closed_at is None or closed_at > moment
                ):
                    return user
        return None

    def resolve(self, character_ids, moment: datetime) -> dict:
        """``{character_id: user}`` for the characters on one killmail."""
        result = {}
        for character_id in character_ids:
            if not character_id:
                continue
            user = self.user_for(character_id, moment)
            if user is not None:
                result[character_id] = user
        return result

    def character_ids(self) -> list[int]:
        """Every character this campaign has ever counted."""
        return list(self._characters)

    def __bool__(self) -> bool:
        return bool(self._characters)


def resolve_attachable_campaign(campaign_id):
    """Resolve an optional campaign id for fleets, orders, posts, timers.

    Returns the campaign, ``None`` when no id was given, or a Ninja
    ``(status, ErrorResponse)`` tuple when the id is unknown or the campaign
    is not open for attachment (scheduled or active only).
    """
    if not campaign_id:
        return None

    campaign = Campaign.objects.filter(id=campaign_id).first()
    if not campaign:
        return 400, ErrorResponse.new(f"No campaign with id {campaign_id}")
    if campaign.status not in (
        CampaignStatus.SCHEDULED,
        CampaignStatus.ACTIVE,
    ):
        return 400, ErrorResponse.new(
            f"Campaign {campaign.slug} is {campaign.status}"
        )
    return campaign


def fill_system_name_from_feed(campaign_system) -> bool:
    """Fill blank names from FeedMonitoredSystem when the id is known."""
    if campaign_system.name and campaign_system.name.strip():
        return False
    if not campaign_system.solar_system_id:
        return False

    known = (
        FeedMonitoredSystem.objects.filter(
            solar_system_id=campaign_system.solar_system_id
        )
        .values_list("name", flat=True)
        .first()
    )
    if not known:
        return False
    campaign_system.name = known
    return True


def ensure_default_arc(campaign_system) -> bool:
    """Create a one-shot arc when an FW objective system has a goal but no arc.

    Operators set goal/role on the campaign change page; arcs live one click
    deeper. Without an arc, advantage week targets never appear. This fills
    the gap with the same defaults seed commands use.
    """
    if not campaign_system.is_fw_objective:
        return False
    if campaign_system.goal in (SystemGoal.NONE, ""):
        return False
    if CampaignSystemArc.objects.filter(
        campaign_system_id=campaign_system.pk
    ).exists():
        return False

    target_state = (
        "hold" if campaign_system.goal == SystemGoal.DEFEND else "flip"
    )
    CampaignSystemArc.objects.create(
        campaign_system=campaign_system,
        target_state=target_state,
        due_at=campaign_system.campaign.end_at,
        contest_ceiling=25.0,
        advantage_floor=10.0,
    )
    return True
