"""One endpoint: see the function below."""

from __future__ import annotations

from authentication import AuthBearer
from campaigns.endpoints import schemas
from campaigns.endpoints.base import router
from campaigns.endpoints.manage import _denied
from campaigns.endpoints.roles_helpers import (
    ROLES_RESPONSE,
    _campaign,
    roles_out,
)
from campaigns.services import roles as role_service


@router.patch(
    "/{slug}/roles/{kind}", response=ROLES_RESPONSE, auth=AuthBearer()
)
def map_role(request, slug: str, kind: str, payload: schemas.CampaignRoleMap):
    """Point a campaign role at a role on the coordination server."""
    campaign, manager, denied = _campaign(request, slug)
    if denied:
        return denied
    if not manager:
        return _denied()
    if kind not in role_service.KINDS:
        return 400, {"detail": "Unknown role."}
    role = next(
        r for r in role_service.ensure_roles(campaign) if r.kind == kind
    )
    try:
        value = (
            int(payload.discord_role_id) if payload.discord_role_id else None
        )
        role_service.set_discord_role(role, value)
    except (ValueError, role_service.RoleError) as error:
        return 400, {"detail": str(error) or "Pick a role."}
    return roles_out(campaign, request.user, manager)
