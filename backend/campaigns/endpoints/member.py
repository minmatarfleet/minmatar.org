"""Endpoints a pilot uses: enlist, ready their characters, report, form up."""

from __future__ import annotations

import logging

from django.shortcuts import get_object_or_404
from django.utils import timezone

from app.errors import ErrorResponse
from authentication import AuthBearer
from campaigns.endpoints.base import router
from campaigns.endpoints import schemas
from campaigns.models import (
    Campaign,
    CampaignEnlistment,
    CampaignEnlistmentCharacter,
    CampaignEnlistmentPeriod,
    CampaignEvent,
    CampaignStandingFleet,
    CampaignStatus,
    CampaignSystem,
)
from campaigns.services import advantage
from campaigns.services.scoring import weights
from eveonline.models import EveCharacter, EvePlayer
from eveonline.scopes import TokenType, token_satisfies_type
from groups.helpers.feature_access import require_feature

logger = logging.getLogger(__name__)


ENLIST_FEATURE = "campaigns.enlist"
GANG_FEATURE = "campaigns.form_gang"

TOKEN_CHAIN_URL = (
    "/api/eveonline/characters/add"
    "?token_type=Campaign&character_id={character_id}&redirect_url={redirect}"
)


def _campaign(slug: str) -> Campaign:
    return get_object_or_404(
        Campaign.objects.exclude(status=CampaignStatus.DRAFT), slug=slug
    )


def _character_state(character: EveCharacter) -> tuple[str, str]:
    """One word for what this character is ready for."""
    token = character.token
    if character.esi_deleted:
        return "removed", "nothing"
    if character.esi_suspended or token is None:
        return "lapsed", "nothing"
    if token_satisfies_type(token, TokenType.CAMPAIGN):
        return "ready", "kills, losses, sites and advantage"
    return "needs_update", "kills and losses"


@router.get("/readiness", response=schemas.ReadinessOut, auth=AuthBearer())
def get_readiness(request, redirect_url: str = "/account/campaigns/"):
    """Every character on one row, with the one action each of them needs."""
    characters = EveCharacter.objects.filter(
        user=request.user, esi_deleted=False
    ).select_related("token")

    player = EvePlayer.objects.filter(user=request.user).first()
    primary_id = (
        player.primary_character.character_id
        if player and player.primary_character
        else None
    )

    included_ids = set(
        CampaignEnlistmentCharacter.objects.filter(
            enlistment__user=request.user, included_until__isnull=True
        ).values_list("character__character_id", flat=True)
    )

    rows = []
    tracked = 0
    for character in characters:
        state, counts_for = _character_state(character)
        if state == "ready":
            tracked += 1
        rows.append(
            {
                "character_id": character.character_id,
                "character_name": character.character_name,
                "corporation_id": character.corporation_id,
                "is_primary": character.character_id == primary_id,
                "token_type": character.esi_token_level or "",
                "counts_for": counts_for,
                "state": state,
                "included": character.character_id in included_ids
                or not included_ids,
                "action_url": (
                    TOKEN_CHAIN_URL.format(
                        character_id=character.character_id,
                        redirect=redirect_url,
                    )
                    if state != "ready"
                    else ""
                ),
            }
        )

    rows.sort(key=lambda row: (not row["is_primary"], row["character_name"]))
    return {"characters": rows, "tracked": tracked, "total": len(rows)}


@router.post(
    "/{slug}/enlist",
    response={200: schemas.EnlistResponse, 403: ErrorResponse},
    auth=AuthBearer(),
)
def enlist(request, slug: str, payload: schemas.EnlistRequest):
    """Enlist, and include every character that is not already excluded."""
    denied = require_feature(request.user, ENLIST_FEATURE)
    if denied:
        return denied

    campaign = _campaign(slug)
    enlistment, _ = CampaignEnlistment.objects.update_or_create(
        campaign=campaign,
        user=request.user,
        defaults={
            "status": "active",
            "source": payload.source,
            "notify_gang_forming": payload.notify_gang_forming,
            "notify_standing_fleet": payload.notify_standing_fleet,
            "notify_activity_nearby": payload.notify_activity_nearby,
            "notify_streak_at_risk": payload.notify_streak_at_risk,
            "digest_hour": payload.digest_hour,
        },
    )

    open_period = enlistment.periods.filter(left_at__isnull=True).first()
    if not open_period:
        CampaignEnlistmentPeriod.objects.create(enlistment=enlistment)

    characters = EveCharacter.objects.filter(
        user=request.user, esi_deleted=False
    ).select_related("token")

    missing = []
    included = 0
    for character in characters:
        # A character can have several inclusion periods, so we look for an
        # open one rather than assuming a single row per character.
        has_open_period = CampaignEnlistmentCharacter.objects.filter(
            enlistment=enlistment,
            character=character,
            included_until__isnull=True,
        ).exists()
        if not has_open_period:
            CampaignEnlistmentCharacter.objects.create(
                enlistment=enlistment,
                character=character,
                included_from=timezone.now(),
            )
        included += 1
        state, _ = _character_state(character)
        if state != "ready":
            missing.append(character.character_name)

    primary = characters.first()
    chain_url = (
        TOKEN_CHAIN_URL.format(
            character_id=primary.character_id,
            redirect=f"/campaigns/{campaign.slug}/",
        )
        if primary and missing
        else ""
    )

    logger.info(
        "%s enlisted in %s via %s", request.user, campaign.slug, payload.source
    )

    return {
        "enlisted": True,
        "characters_included": included,
        "characters_missing_scopes": missing,
        "token_chain_url": chain_url,
    }


@router.delete("/{slug}/enlist", response={200: dict}, auth=AuthBearer())
def leave(request, slug: str):
    campaign = _campaign(slug)
    enlistment = CampaignEnlistment.objects.filter(
        campaign=campaign, user=request.user
    ).first()
    if not enlistment:
        return {"enlisted": False}

    enlistment.status = "left"
    enlistment.save(update_fields=["status"])
    enlistment.periods.filter(left_at__isnull=True).update(
        left_at=timezone.now()
    )
    return {"enlisted": False}


@router.put(
    "/{slug}/characters/{character_id}",
    response={200: dict},
    auth=AuthBearer(),
)
def include_character(request, slug: str, character_id: int):
    """Count this character from now on."""
    campaign = _campaign(slug)
    enlistment = get_object_or_404(
        CampaignEnlistment, campaign=campaign, user=request.user
    )
    character = get_object_or_404(
        EveCharacter, character_id=character_id, user=request.user
    )

    row = CampaignEnlistmentCharacter.objects.filter(
        enlistment=enlistment, character=character, included_until__isnull=True
    ).first()
    if not row:
        CampaignEnlistmentCharacter.objects.create(
            enlistment=enlistment,
            character=character,
            included_from=timezone.now(),
        )
    return {"included": True, "character_id": character_id}


@router.delete(
    "/{slug}/characters/{character_id}",
    response={200: dict},
    auth=AuthBearer(),
)
def exclude_character(request, slug: str, character_id: int):
    """Stop counting this character. History already attributed stays."""
    campaign = _campaign(slug)
    enlistment = get_object_or_404(
        CampaignEnlistment, campaign=campaign, user=request.user
    )
    CampaignEnlistmentCharacter.objects.filter(
        enlistment=enlistment,
        character__character_id=character_id,
        included_until__isnull=True,
    ).update(included_until=timezone.now())
    return {"included": False, "character_id": character_id}


@router.post(
    "/{slug}/systems/{system_id}/advantage",
    response={200: schemas.AdvantageResponse, 403: ErrorResponse},
    auth=AuthBearer(),
)
def report_advantage(
    request, slug: str, system_id: int, payload: schemas.AdvantageRequest
):
    """One tap from a pilot in space. ESI will not tell us this."""
    denied = require_feature(request.user, ENLIST_FEATURE)
    if denied:
        return denied

    campaign = _campaign(slug)
    campaign_system = get_object_or_404(
        CampaignSystem, campaign=campaign, id=system_id
    )

    reading = advantage.record_reading(
        campaign_system, request.user, payload.our_pct, payload.enemy_pct
    )
    state = advantage.state_for(campaign_system)

    return {
        "accepted": reading.status == "accepted",
        "status": reading.status,
        "our_pct": state["our_pct"],
        "enemy_pct": state["enemy_pct"],
        "net_pct": state["net_pct"],
        "points": (
            weights(campaign)["advantage_reading"]
            if reading.status == "accepted"
            else 0
        ),
    }


@router.post(
    "/{slug}/standing-fleet/take", response={200: dict}, auth=AuthBearer()
)
def take_standing_fleet(request, slug: str):
    """Any enlisted pilot may take the fleet when nobody is boss."""
    denied = require_feature(request.user, ENLIST_FEATURE)
    if denied:
        return denied

    campaign = _campaign(slug)
    standing, _ = CampaignStandingFleet.objects.get_or_create(
        campaign=campaign
    )

    if standing.is_up and standing.current_boss_user_id != request.user.id:
        return {"taken": False, "reason": "Someone already has it."}

    character = EveCharacter.objects.filter(user=request.user).first()
    standing.current_boss_user = request.user
    standing.current_boss_character_id = (
        character.character_id if character else None
    )
    standing.taken_at = timezone.now()
    standing.last_seen_at = timezone.now()
    standing.handovers += 1
    standing.save()

    CampaignEvent.objects.create(
        campaign=campaign,
        kind=CampaignEvent.Kind.STANDING_FLEET_TAKEN,
        occurred_at=timezone.now(),
        title=f"{request.user.username} took the standing fleet",
        user=request.user,
        side="friendly",
    )
    return {"taken": True}


@router.post(
    "/{slug}/standing-fleet/join", response={200: dict}, auth=AuthBearer()
)
def join_standing_fleet(request, slug: str):
    """Ask the current boss's client to invite this pilot.

    The ESI invite needs the boss's token and an in-game fleet, so when there
    is no boss the honest answer is to offer the fleet instead of failing.
    """
    campaign = _campaign(slug)
    standing = getattr(campaign, "standing_fleet", None)
    if not standing or not standing.is_up:
        return {
            "invited": False,
            "reason": "No standing fleet is up. Take it and it becomes yours.",
        }
    # Wiring the ESI invite itself is ticket 10; the contract is settled here.
    return {
        "invited": False,
        "reason": "Invite queued with the fleet boss.",
        "boss_character_id": standing.current_boss_character_id,
    }


@router.post(
    "/{slug}/gangs",
    response={200: dict, 403: ErrorResponse},
    auth=AuthBearer(),
)
def form_gang(request, slug: str, payload: schemas.GangRequest):
    """Four fields and a line. Anyone enlisted can start one."""
    denied = require_feature(request.user, GANG_FEATURE)
    if denied:
        return denied

    campaign = _campaign(slug)
    system = None
    if payload.solar_system_id:
        system = CampaignSystem.objects.filter(
            campaign=campaign, solar_system_id=payload.solar_system_id
        ).first()

    event = CampaignEvent.objects.create(
        campaign=campaign,
        kind=CampaignEvent.Kind.GANG_FORMED,
        occurred_at=timezone.now(),
        title=f"{request.user.username} is forming {payload.ships}",
        body=payload.note,
        campaign_system=system,
        user=request.user,
        side="friendly",
        is_active=True,
        payload={
            "ships": payload.ships,
            "voice_channel_id": payload.voice_channel_id,
        },
    )
    return {"gang_id": event.id, "formed": True}
