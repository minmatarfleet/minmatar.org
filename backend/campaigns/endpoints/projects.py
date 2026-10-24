"""Corporation projects put toward a campaign.

A director picks one of their corporation's in-game projects and attaches
it. No approval: the corporation funds the project, the campaign only shows
it. Campaign managers can take one off.
"""

from __future__ import annotations

from uuid import UUID

from django.shortcuts import get_object_or_404
from ninja import Schema

from app.errors import ErrorResponse
from authentication import AuthBearer, AuthOptional
from campaigns.endpoints.base import router
from campaigns.endpoints.manage import _can_manage
from campaigns.endpoints.public import _get, _may_read
from campaigns.models import CampaignProject
from eveonline.endpoints.corporations.schemas import CorporationProject
from eveonline.helpers.corporations.permissions import (
    can_manage_corporation_projects,
)
from eveonline.helpers.corporations.projects import project_out
from eveonline.models import EveCorporationProject


class AttachProjectRequest(Schema):
    project_id: UUID


@router.get(
    "/{slug}/projects",
    response={200: list[CorporationProject], 403: ErrorResponse, 404: None},
    auth=AuthOptional(),
)
def get_campaign_projects(request, slug: str):
    """Every attached project, finished ones included, with contributors."""
    campaign = _get(request, slug)
    denied = _may_read(request, campaign)
    if denied:
        return denied
    links = (
        CampaignProject.objects.filter(campaign=campaign)
        .select_related("project__corporation")
        .prefetch_related("project__contributors")
    )
    return [project_out(link.project) for link in links]


@router.post(
    "/{slug}/projects",
    response={
        201: None,
        200: None,
        400: ErrorResponse,
        403: ErrorResponse,
        404: None,
    },
    auth=AuthBearer(),
)
def attach_campaign_project(request, slug: str, payload: AttachProjectRequest):
    campaign = _get(request, slug)
    project = get_object_or_404(
        EveCorporationProject.objects.select_related("corporation"),
        project_id=payload.project_id,
    )
    if not can_manage_corporation_projects(request.user, project.corporation):
        return 403, ErrorResponse(detail="Not authorised")
    if not campaign.is_counting:
        return 400, ErrorResponse(detail="campaign_not_open")
    _, created = CampaignProject.objects.get_or_create(
        campaign=campaign,
        project=project,
        defaults={"attached_by": request.user},
    )
    return (201 if created else 200), None


@router.delete(
    "/{slug}/projects/{project_id}",
    response={204: None, 403: ErrorResponse, 404: None},
    auth=AuthBearer(),
)
def detach_campaign_project(request, slug: str, project_id: UUID):
    campaign = _get(request, slug)
    link = get_object_or_404(
        CampaignProject.objects.select_related("project__corporation"),
        campaign=campaign,
        project_id=project_id,
    )
    corporation = link.project.corporation
    if not (
        can_manage_corporation_projects(request.user, corporation)
        or _can_manage(request.user, campaign)
    ):
        return 403, ErrorResponse(detail="Not authorised")
    link.delete()
    return 204, None
