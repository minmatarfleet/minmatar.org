"""Invite characters from outside the alliance to help run a campaign.

A coordinator is invited by character name, whether or not the character
has ever signed in to the site. The site's own characters resolve locally;
anyone else resolves through ESI's exact-name lookup.
"""

from __future__ import annotations

import logging

from django.utils import timezone

from campaigns.models import Campaign, CampaignCoordinator
from eveonline.client import EsiClient
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCorporation,
    EvePlayer,
)

logger = logging.getLogger(__name__)


class NotFound(Exception):
    """No character has exactly that name."""


def _names(corporation_id, alliance_id) -> tuple[str, str]:
    corporation = (
        EveCorporation.objects.filter(corporation_id=corporation_id)
        .values_list("name", flat=True)
        .first()
        if corporation_id
        else None
    )
    alliance = (
        EveAlliance.objects.filter(alliance_id=alliance_id)
        .values_list("name", flat=True)
        .first()
        if alliance_id
        else None
    )
    missing = [
        entity_id
        for entity_id, name in (
            (corporation_id, corporation),
            (alliance_id, alliance),
        )
        if entity_id and not name
    ]
    if missing:
        response = EsiClient(None).resolve_universe_names(missing)
        if response.success():
            found = {
                row["id"]: row.get("name", "")
                for row in response.results() or []
            }
            corporation = corporation or found.get(corporation_id)
            alliance = alliance or found.get(alliance_id)
    return corporation or "", alliance or ""


def lookup(name: str) -> dict:
    """The character called ``name``: id, exact name, corporation, alliance.

    Raises NotFound when neither the site nor ESI knows the name.
    """
    name = name.strip()
    local = EveCharacter.objects.filter(character_name__iexact=name).first()
    if local is not None:
        corporation, alliance = _names(local.corporation_id, local.alliance_id)
        return {
            "character_id": local.character_id,
            "character_name": local.character_name,
            "corporation_name": corporation,
            "alliance_name": alliance,
        }

    response = EsiClient(None).resolve_universe_ids([name])
    if not response.success():
        raise NotFound(name)
    data = response.data if isinstance(response.data, dict) else {}
    characters = data.get("characters") or []
    if not characters:
        raise NotFound(name)
    character = characters[0]
    character_id = int(character["id"])

    corporation_id = alliance_id = None
    affiliation = EsiClient(None).get_character_affiliations([character_id])
    if affiliation.success():
        rows = affiliation.results() or []
        if rows:
            corporation_id = rows[0].get("corporation_id")
            alliance_id = rows[0].get("alliance_id")
    corporation, alliance = _names(corporation_id, alliance_id)
    return {
        "character_id": character_id,
        "character_name": character.get("name") or name,
        "corporation_name": corporation,
        "alliance_name": alliance,
    }


def invite(campaign: Campaign, name: str, user) -> CampaignCoordinator:
    found = lookup(name)
    coordinator = CampaignCoordinator.objects.update_or_create(
        campaign=campaign,
        character_id=found["character_id"],
        defaults={
            "character_name": found["character_name"],
            "corporation_name": found["corporation_name"],
            "alliance_name": found["alliance_name"],
            "invited_by": user,
        },
    )[0]
    logger.info(
        "Campaign %s: %s invited coordinator %s",
        campaign.id,
        getattr(user, "id", None),
        found["character_id"],
    )
    notify(coordinator)
    return coordinator


def _owner(character_id: int):
    character = (
        EveCharacter.objects.filter(
            character_id=character_id, user__isnull=False
        )
        .select_related("user")
        .first()
    )
    return character.user if character else None


def _inviter_name(user) -> str:
    if user is None:
        return ""
    player = (
        EvePlayer.objects.filter(user=user)
        .select_related("primary_character")
        .first()
    )
    if player and player.primary_character:
        return player.primary_character.character_name
    return user.username


def notify(coordinator: CampaignCoordinator) -> bool:
    """DM the character's owner that they coordinate the campaign, once.

    Nobody to tell until someone owns the character on the site; the
    character signal (``campaigns.signals``) tries again then.
    """
    # pylint: disable=import-outside-toplevel
    from campaigns.services.discord_posts import (
        POSTING_STATUSES,
        campaign_url,
    )
    from notifications.service import notify_user
    from notifications.types.campaigns import (
        CAMPAIGN_COORDINATOR_INVITED_KEY,
    )

    if coordinator.invite_notified_at is not None:
        return False
    campaign = coordinator.campaign
    if campaign.status not in POSTING_STATUSES:
        return False
    user = _owner(coordinator.character_id)
    if user is None:
        return False
    notify_user(
        user,
        CAMPAIGN_COORDINATOR_INVITED_KEY,
        {
            "campaign_name": campaign.name,
            "character_name": coordinator.character_name,
            "inviter": _inviter_name(coordinator.invited_by),
            "url": campaign_url(campaign),
        },
        idempotency_key=(
            f"{CAMPAIGN_COORDINATOR_INVITED_KEY}:{coordinator.id}"
        ),
    )
    coordinator.invite_notified_at = timezone.now()
    coordinator.save(update_fields=["invite_notified_at"])
    return True


def notify_pending(character) -> int:
    """Send the invite DMs a newly owned character was waiting for."""
    pending = CampaignCoordinator.objects.filter(
        character_id=character.character_id, invite_notified_at__isnull=True
    ).select_related("campaign", "invited_by")
    return sum(1 for coordinator in pending if notify(coordinator))
