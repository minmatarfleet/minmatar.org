"""One endpoint: see the function below."""

from __future__ import annotations

import logging

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

logger = logging.getLogger(__name__)


@router.post(
    "/{slug}/roles/{kind}/members", response=ROLES_RESPONSE, auth=AuthBearer()
)
def add_role_member(
    request, slug: str, kind: str, payload: schemas.CampaignRoleAdd
):
    """Add a role holder: a member of the coordination server
    (``discord_user_id``, from the suggestions; they get the Discord role at
    once), or anyone by exact character name (they get it on the next sync
    once they have linked Discord). The owner of the character is told."""
    campaign, manager, denied = _campaign(request, slug)
    if denied:
        return denied
    if not _can_edit(request.user, campaign, "roles"):
        return _denied()
    name = payload.character_name.strip()
    try:
        if payload.discord_user_id:
            if not payload.discord_user_id.isdigit():
                return 400, {"detail": "Unknown Discord member."}
            role_service.add_discord_member(
                campaign,
                kind,
                int(payload.discord_user_id),
                request.user,
                character_name=name,
            )
        elif len(name) < 3:
            return 400, {"detail": "No character has that exact name."}
        else:
            role_service.add_character(campaign, kind, name, request.user)
    except role_service.RoleError as error:
        return 400, {"detail": str(error)}
    # pylint: disable-next=import-outside-toplevel
    from campaigns.tasks import sync_campaign_roles

    # The holder is saved; the 15-minute sync catches up if the queue is down.
    try:
        sync_campaign_roles.delay(campaign.id)
    except Exception:  # pylint: disable=broad-except
        logger.warning("Campaign %s: could not queue a role sync", campaign.id)
    return roles_out(campaign, request.user, manager)
