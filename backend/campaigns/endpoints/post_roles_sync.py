"""One endpoint: see the function below."""

from __future__ import annotations

import logging

from authentication import AuthBearer
from campaigns.endpoints.base import router
from campaigns.endpoints.manage import _can_edit, _denied
from campaigns.endpoints.roles_helpers import (
    ROLES_RESPONSE,
    _campaign,
    roles_out,
)
from campaigns.services import roles as role_service

logger = logging.getLogger(__name__)


@router.post("/{slug}/roles/sync", response=ROLES_RESPONSE, auth=AuthBearer())
def sync_roles(request, slug: str):
    """Read the coordination server now instead of waiting for the beat."""
    campaign, manager, denied = _campaign(request, slug)
    if denied:
        return denied
    if not _can_edit(request.user, campaign, "roles"):
        return _denied()
    try:
        role_service.sync(campaign)
    except role_service.RoleError as error:
        return 400, {"detail": str(error)}
    except Exception:  # pylint: disable=broad-except
        logger.warning(
            "Campaign %s role sync failed", campaign.id, exc_info=True
        )
        return 400, {"detail": "Discord did not answer. Try again shortly."}
    return roles_out(campaign, request.user, manager)
