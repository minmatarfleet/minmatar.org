"""Shared fixtures for campaign tests."""

from __future__ import annotations

from datetime import timedelta

import jwt
from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.utils import timezone

from campaigns.models import (
    Campaign,
    CampaignEnlistment,
    CampaignEnlistmentCharacter,
    CampaignEnlistmentPeriod,
    CampaignStatus,
    CampaignSystem,
    SystemGoal,
    SystemRole,
)
from eveonline.models import EveCharacter
from feed.models import FeedKillmail

KAMELA = 30003069
KOURMONEN = 30003068


def make_campaign(**overrides) -> Campaign:
    now = timezone.now()
    defaults = {
        "slug": "test-push",
        "short_code": "TST",
        "name": "Test Push",
        "status": CampaignStatus.ACTIVE,
        "start_at": now - timedelta(days=7),
        "end_at": now + timedelta(days=7),
    }
    defaults.update(overrides)
    campaign = Campaign.objects.create(**defaults)
    CampaignSystem.objects.create(
        campaign=campaign,
        solar_system_id=KAMELA,
        name="Kamela",
        goal=SystemGoal.CAPTURE,
        role=SystemRole.PRIMARY,
    )
    return campaign


def enlist(campaign: Campaign, username: str, character_id: int, **kwargs):
    """Create a user with one character and enlist them."""
    user = User.objects.create(username=username)
    character = EveCharacter.objects.create(
        character_id=character_id,
        character_name=username.title(),
        user=user,
    )
    enlistment = CampaignEnlistment.objects.create(
        campaign=campaign, user=user, status="active"
    )
    CampaignEnlistmentPeriod.objects.create(
        enlistment=enlistment,
        enlisted_at=kwargs.get("enlisted_at", campaign.start_at),
        left_at=kwargs.get("left_at"),
    )
    CampaignEnlistmentCharacter.objects.create(
        enlistment=enlistment,
        character=character,
        included_from=kwargs.get("included_from", campaign.start_at),
        included_until=kwargs.get("included_until"),
    )
    return user, character


def make_feed_killmail(
    killmail_id: int,
    *,
    solar_system_id: int = KAMELA,
    victim_character_id: int | None = None,
    attacker_ids: list[int] | None = None,
    killmail_time=None,
    isk_value: int = 50_000_000,
    ship_type_id: int = 587,
):
    """A FeedKillmail shaped like the real zKill payload."""
    killmail_time = killmail_time or timezone.now()
    attackers = [
        {
            "character_id": character_id,
            "corporation_id": 98000001,
            "ship_type_id": 621,
            "damage_done": 1000,
            "final_blow": index == 0,
        }
        for index, character_id in enumerate(attacker_ids or [])
    ]

    return FeedKillmail.objects.create(
        killmail_id=killmail_id,
        hash="abc123",
        killmail_time=killmail_time,
        solar_system_id=solar_system_id,
        victim_character_id=victim_character_id,
        victim_ship_type_id=ship_type_id,
        attacker_summary=attackers,
        raw_killmail={
            "killmail_id": killmail_id,
            "killmail_time": killmail_time.isoformat(),
            "solar_system_id": solar_system_id,
            "victim": {
                "character_id": victim_character_id,
                "corporation_id": 98000002,
                "ship_type_id": ship_type_id,
            },
            "attackers": attackers,
        },
        zkb_meta={"totalValue": isk_value, "solo": len(attackers) == 1},
    )


def auth_headers(user: User) -> dict:
    """Bearer header for a user, the way the site signs its own tokens."""
    token = jwt.encode(
        {"user_id": user.pk}, settings.SECRET_KEY, algorithm="HS256"
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def grant(user: User, *codenames: str) -> None:
    """Give a user the legacy permissions a campaign feature falls back to."""
    for codename in codenames:
        permission = Permission.objects.filter(
            content_type__app_label="campaigns", codename=codename
        ).first()
        if permission:
            user.user_permissions.add(permission)
    user.refresh_from_db()
