"""One endpoint: see the function below."""

from __future__ import annotations

from django.db import transaction
from django.shortcuts import get_object_or_404

from app.errors import ErrorResponse
from authentication import AuthBearer
from campaigns.endpoints import schemas
from campaigns.endpoints.base import router
from campaigns.endpoints.coordinator_helpers import _managed
from campaigns.endpoints.settings_helpers import coordinators_out
from campaigns.models import CampaignCoordinator
from campaigns.services import discord_posts
from eveonline.models import EveCharacter


@router.delete(
    "/{slug}/coordinators/{coordinator_id}",
    response={
        200: list[schemas.CampaignCoordinatorOut],
        403: ErrorResponse,
        404: None,
    },
    auth=AuthBearer(),
)
def remove_coordinator(request, slug: str, coordinator_id: int):
    """Take a coordinator off the campaign, and the servers they linked."""
    campaign, denied = _managed(request, slug)
    if denied:
        return denied
    coordinator = get_object_or_404(
        CampaignCoordinator, campaign=campaign, id=coordinator_id
    )
    owners = list(
        EveCharacter.objects.filter(
            character_id=coordinator.character_id, user__isnull=False
        ).values_list("user_id", flat=True)
    )
    with transaction.atomic():
        campaign.discord_links.filter(linked_by_id__in=owners).delete()
        coordinator.delete()
    discord_posts.queue_all_board_refreshes(campaign.id)
    return coordinators_out(campaign)
