"""GET /corporations/{corporation_id}/projects - in-game corporation projects."""

from ninja import Router

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.corporations.schemas import (
    CorporationProjectsResponse,
)
from eveonline.helpers.corporations import projects
from eveonline.helpers.corporations.permissions import (
    can_manage_corporation_projects,
    can_view_corporation_projects,
)
from eveonline.helpers.corporations.profile import load_corporation
from eveonline.models import EveCorporationProject

router = Router(tags=["Corporations"])


def _campaign_ref(campaign) -> dict:
    return {
        "slug": campaign.slug,
        "name": campaign.name,
        "status": campaign.status,
    }


@router.get(
    "corporations/{corporation_id}/projects",
    response={
        200: CorporationProjectsResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="A corporation's in-game projects (leadership only)",
)
def get_corporation_projects(request, corporation_id: int):
    # Campaigns import eveonline models; keep this module importable first.
    from campaigns.models import (  # pylint: disable=import-outside-toplevel
        Campaign,
        CampaignProject,
        CampaignStatus,
    )

    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_view_corporation_projects(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")

    rows = list(
        EveCorporationProject.objects.filter(corporation=corporation)
        .select_related("corporation")
        .prefetch_related("contributors")
    )
    attached = {}
    for link in CampaignProject.objects.filter(
        project__in=rows
    ).select_related("campaign"):
        attached.setdefault(link.project_id, []).append(
            _campaign_ref(link.campaign)
        )
    open_campaigns = Campaign.objects.filter(
        status__in=[CampaignStatus.SCHEDULED, CampaignStatus.ACTIVE]
    ).order_by("start_at")

    return {
        "corporation_id": corporation.corporation_id,
        "can_manage": can_manage_corporation_projects(
            request.user, corporation
        ),
        "has_token": projects.projects_scope_holder(corporation) is not None,
        "synced_at": projects.last_synced(corporation.corporation_id),
        "refreshing": projects.is_refreshing(corporation.corporation_id),
        "projects": [
            projects.project_out(row, attached.get(row.project_id))
            for row in rows
        ],
        "campaigns": [_campaign_ref(c) for c in open_campaigns],
    }


@router.post(
    "corporations/{corporation_id}/projects/refresh",
    response={
        202: None,
        403: ErrorResponse,
        404: ErrorResponse,
        409: ErrorResponse,
        429: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Queue a projects sync from ESI (CEO and directors)",
)
def refresh_corporation_projects(request, corporation_id: int):
    # Tasks import this router's helpers; import late to avoid a cycle.
    from eveonline.tasks.corporations import (  # pylint: disable=import-outside-toplevel
        sync_corporation_projects,
    )

    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_manage_corporation_projects(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    if projects.projects_scope_holder(corporation) is None:
        return 409, ErrorResponse(detail="no_token")
    if not projects.mark_refreshing(corporation.corporation_id):
        return 429, ErrorResponse(detail="refresh_pending")
    sync_corporation_projects.apply_async(args=[corporation.corporation_id])
    return 202, None
