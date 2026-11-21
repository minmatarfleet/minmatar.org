"""One endpoint: see the function below."""

from __future__ import annotations

from django.shortcuts import get_object_or_404

from app.errors import ErrorResponse
from authentication import AuthBearer
from campaigns.endpoints import schemas
from campaigns.endpoints.base import router
from campaigns.models import Campaign
from campaigns.services import coordination, disclosure


@router.get(
    "/{slug}/discord-links",
    response={
        200: list[schemas.CampaignDiscordLinkOut],
        403: ErrorResponse,
        404: None,
    },
    auth=AuthBearer(),
)
def list_links(request, slug: str):
    """The servers this viewer may edit: all of them for managers, a
    coordinator's own for a coordinator."""
    campaign = get_object_or_404(Campaign, slug=slug)
    viewer = disclosure.role(request.user, campaign)
    if viewer == disclosure.MEMBER:
        return 403, {"detail": "Not authorised"}
    links = campaign.discord_links.select_related("linked_by")
    if viewer == disclosure.COORDINATOR:
        links = links.filter(linked_by=request.user)
    return [coordination.link_out(link) for link in links]
