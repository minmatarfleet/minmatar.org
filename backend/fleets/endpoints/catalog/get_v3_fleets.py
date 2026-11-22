"""GET /v3 — full fleet cards (requires fleets.view_evefleet)."""

from datetime import timedelta
from typing import List, Optional, Union

from django.db.models import Q
from django.utils import timezone

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import fleet_audience_q, require_feature

from fleets.endpoints.helpers import (
    FLEET_RESPONSE_RELATED,
    is_strategic_fc,
    make_fleet_response,
)
from fleets.endpoints.schemas import EveFleetFilter, EveFleetResponse
from fleets.helpers.visibility import visible_fleets_q
from fleets.models import CAMPAIGN_FLEET_TYPES, EveFleet

PATH = "/v3"
METHOD = "get"
ROUTE_SPEC = {
    "response": {
        200: List[EveFleetResponse],
        401: ErrorResponse,
        403: ErrorResponse,
    },
    "auth": AuthBearer(),
    "description": (
        "List fleets matching the filter. Requires fleets.view_evefleet. "
        "A fleet is listed only when GET /api/fleets/{id} would show it: "
        "its audience includes the viewer, and tribe group fleets when "
        "the viewer can see them; "
        "host_group_id lists one group's fleets; campaign_id lists the "
        "fleets linked to one campaign (recent: the whole campaign, not "
        "just the last 30 days)."
    ),
}


def _sees_campaign(user, campaign_id: int) -> bool:
    # pylint: disable=import-outside-toplevel
    from campaigns.models import Campaign
    from campaigns.services.disclosure import sees_details

    campaign = Campaign.objects.filter(id=campaign_id).first()
    return campaign is None or sees_details(user, campaign)


def get_v3_fleets(
    request,
    fleet_filter: EveFleetFilter = EveFleetFilter.RECENT,
    host_group_id: Optional[int] = None,
    campaign_id: Optional[int] = None,
) -> Union[List[EveFleetResponse], tuple[int, dict]]:
    denied = require_feature(request.user, "fleets.view")
    if denied and not is_strategic_fc(request.user):
        return denied

    if fleet_filter == EveFleetFilter.ACTIVE:
        fleets = (
            EveFleet.objects.filter(evefleetinstance__end_time=None)
            .filter(
                Q(
                    status__in=["cancelled", "pending"],
                    start_time__gte=timezone.now() - timedelta(hours=1),
                )
                | Q(
                    ~Q(status__in=["cancelled", "pending"]),
                    start_time__gte=timezone.now() - timedelta(hours=24),
                )
            )
            .order_by("-start_time")
        )
    elif fleet_filter == EveFleetFilter.UPCOMING:
        fleets = (
            EveFleet.objects.filter(status="pending")
            .filter(
                Q(evefleetinstance__isnull=True)
                | Q(evefleetinstance__end_time__isnull=False)
            )
            .order_by("start_time")
        )
    elif campaign_id:
        # A campaign's history runs as long as the campaign.
        fleets = EveFleet.objects.filter(
            start_time__lte=timezone.now()
        ).order_by("-start_time")
    else:
        fleets = EveFleet.objects.filter(
            start_time__gte=timezone.now() - timedelta(days=30)
        ).order_by("-start_time")

    if campaign_id:
        fleets = fleets.filter(campaign_id=campaign_id)
        if not _sees_campaign(request.user, campaign_id):
            # An undisclosed campaign's fleets are for those who may see it.
            fleets = fleets.none()
    if host_group_id:
        fleets = fleets.filter(host_group_id=host_group_id)
    if not is_strategic_fc(request.user):
        # Group fleets have no audience; an alliance fleet still needs a
        # visible one, as before, and one whose groups include the viewer.
        # The creator always sees their own fleet, as the detail endpoint
        # lets them open it (_fleet_authorized). Strategic FCs see every
        # fleet.
        fleets = fleets.filter(
            Q(audience__hidden=False)
            | Q(host_group__isnull=False)
            | Q(created_by_id=request.user.pk)
        )
        audience_q = fleet_audience_q(request.user)
        if audience_q:  # an empty Q means every audience
            fleets = fleets.filter(
                audience_q | Q(created_by_id=request.user.pk)
            )
    fleets = (
        fleets.filter(visible_fleets_q(request.user))
        .exclude(type__in=CAMPAIGN_FLEET_TYPES)
        .select_related(*FLEET_RESPONSE_RELATED)
    )
    return [make_fleet_response(fleet) for fleet in fleets]
