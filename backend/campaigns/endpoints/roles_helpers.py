"""Shared by the campaign roles endpoints (Coordinator, FC, Diplomat, Recon).

Discord decides (``services.roles``). Managers and role holders read the
rosters; managers and Coordinators add, remove and sync; managers point a
role at a Discord role.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404

from app.errors import ErrorResponse
from campaigns.endpoints import schemas
from campaigns.endpoints.manage import _can_edit, _can_manage, _denied
from campaigns.models import (
    Campaign,
    CampaignRoleKind,
    CampaignRoleMember,
)
from campaigns.services import roles as role_service

LABELS = dict(CampaignRoleKind.choices)


def _campaign(request, slug: str):
    """The campaign and what the caller may do, or a 403/404."""
    campaign = get_object_or_404(Campaign, slug=slug)
    manager = _can_manage(request.user, campaign)
    if not manager and not role_service.kinds_for(request.user, campaign):
        return campaign, None, _denied()
    return campaign, manager, None


def _id(value) -> str | None:
    return str(value) if value else None


def roles_out(campaign: Campaign, user, manager: bool) -> dict:
    rows = role_service.ensure_roles(campaign)
    members = {}
    for member in CampaignRoleMember.objects.filter(
        role__campaign=campaign
    ).select_related("role"):
        members.setdefault(member.role_id, []).append(member)
    return {
        "roles": [
            {
                "kind": role.kind,
                "label": LABELS[role.kind],
                "discord_role_id": _id(role.discord_role_id),
                "discord_role_name": role.discord_role_name,
                "synced_at": role.synced_at,
                "sync_error": role.sync_error,
                "reads": sorted(role_service.READS[role.kind]),
                "edits": sorted(role_service.EDITS[role.kind]),
                "members": [
                    {
                        "id": member.id,
                        "source": member.source,
                        "discord_user_id": _id(member.discord_user_id),
                        "discord_name": member.discord_name,
                        "character_id": member.character_id,
                        "character_name": member.character_name,
                        "corporation_name": member.corporation_name,
                        "alliance_name": member.alliance_name,
                        "signed_in": member.user_id is not None,
                    }
                    for member in members.get(role.id, [])
                ],
            }
            for role in rows
        ],
        "can_change": _can_edit(user, campaign, "roles"),
        "can_map": manager,
        "discord_roles": (
            role_service.discord_roles(campaign) if manager else []
        ),
    }


ROLES_RESPONSE = {
    200: schemas.CampaignRolesOut,
    400: ErrorResponse,
    403: ErrorResponse,
    404: None,
}
