"""One endpoint: see the function below."""

from __future__ import annotations

from django.shortcuts import get_object_or_404

from authentication import AuthBearer
from campaigns.endpoints.base import router
from campaigns.endpoints.manage import _can_edit, _denied
from campaigns.endpoints.roles_helpers import (
    ROLES_RESPONSE,
    _campaign,
    roles_out,
)
from campaigns.models import CampaignRoleMember
from campaigns.services import roles as role_service


@router.delete(
    "/{slug}/roles/{kind}/members/{member_id}",
    response=ROLES_RESPONSE,
    auth=AuthBearer(),
)
def remove_role_member(request, slug: str, kind: str, member_id: int):
    """Take the role away, here and on the coordination server."""
    campaign, manager, denied = _campaign(request, slug)
    if denied:
        return denied
    if not _can_edit(request.user, campaign, "roles"):
        return _denied()
    member = get_object_or_404(
        CampaignRoleMember,
        id=member_id,
        role__campaign=campaign,
        role__kind=kind,
    )
    try:
        role_service.remove_member(member)
    except role_service.RoleError as error:
        return 400, {"detail": str(error)}
    return roles_out(campaign, request.user, manager)
