"""One endpoint: see the function below."""

from __future__ import annotations

from django.shortcuts import get_object_or_404

from app.errors import ErrorResponse
from authentication import AuthBearer
from campaigns.endpoints.base import router
from campaigns.endpoints.discord_link_helpers import _may_edit
from campaigns.models import CampaignDiscordLink


@router.delete(
    "/{slug}/discord-links/{link_id}",
    response={204: None, 403: ErrorResponse, 404: None},
    auth=AuthBearer(),
)
def remove_link(request, slug: str, link_id: int):
    """Stop forwarding to a linked server."""
    link = get_object_or_404(
        CampaignDiscordLink.objects.select_related("campaign"),
        campaign__slug=slug,
        id=link_id,
    )
    if not _may_edit(request.user, link):
        return 403, {"detail": "Not authorised"}
    link.delete()
    return 204, None
