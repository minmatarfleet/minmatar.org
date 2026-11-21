"""One endpoint: see the function below."""

from __future__ import annotations

from django.shortcuts import get_object_or_404

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import require_feature

from campaigns.endpoints import schemas
from campaigns.endpoints.base import router
from campaigns.endpoints.manage import _can_manage, _denied
from campaigns.models import Campaign
from campaigns.services import coordination


@router.get(
    "/{slug}/coordination",
    response={
        200: schemas.CampaignCoordinationOut,
        403: ErrorResponse,
        404: None,
    },
    auth=AuthBearer(),
)
def get_coordination(request, slug: str, guild_id: str = ""):
    """The campaign's coordination Discord server and channels. Admins
    only: nobody else sees which server a campaign is run from.
    ``guild_id`` lists another server's channels while choosing one."""
    denied = require_feature(request.user, coordination.FEATURE)
    if denied:
        return denied
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()
    server_id = int(guild_id) if guild_id.isdigit() else None
    if server_id and not coordination.is_bot_server(server_id):
        server_id = None
    return coordination.coordination_out(campaign, server_id)
