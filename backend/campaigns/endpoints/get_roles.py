"""One endpoint: see the function below."""

from __future__ import annotations

from authentication import AuthBearer
from campaigns.endpoints.base import router
from campaigns.endpoints.roles_helpers import (
    ROLES_RESPONSE,
    _campaign,
    roles_out,
)


@router.get("/{slug}/roles", response=ROLES_RESPONSE, auth=AuthBearer())
def get_roles(request, slug: str):
    """The four campaign roles and who holds each."""
    campaign, manager, denied = _campaign(request, slug)
    if denied:
        return denied
    return roles_out(campaign, request.user, manager)
