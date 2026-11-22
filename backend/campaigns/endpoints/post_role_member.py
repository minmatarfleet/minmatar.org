"""One endpoint: see the function below."""

from __future__ import annotations

from authentication import AuthBearer
from campaigns.endpoints import schemas
from campaigns.endpoints.base import router
from campaigns.endpoints.manage import _can_edit, _denied
from campaigns.endpoints.roles_helpers import (
    ROLES_RESPONSE,
    _campaign,
    roles_out,
)
from campaigns.services import roles as role_service


@router.post(
    "/{slug}/roles/{kind}/members", response=ROLES_RESPONSE, auth=AuthBearer()
)
def add_role_member(
    request, slug: str, kind: str, payload: schemas.CampaignRoleAdd
):
    """Add a role holder by exact character name. They get the Discord role
    on the next sync once they have linked Discord."""
    campaign, manager, denied = _campaign(request, slug)
    if denied:
        return denied
    if not _can_edit(request.user, campaign, "roles"):
        return _denied()
    try:
        role_service.add_character(
            campaign, kind, payload.character_name, request.user
        )
    except role_service.RoleError as error:
        return 400, {"detail": str(error)}
    # pylint: disable-next=import-outside-toplevel
    from campaigns.tasks import sync_campaign_roles

    sync_campaign_roles.delay(campaign.id)
    return roles_out(campaign, request.user, manager)
