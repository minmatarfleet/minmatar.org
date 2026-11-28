"""POST /corporations/{corporation_id}/refresh - re-read the corp from ESI."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.corporations.schemas import CorporationRefreshResponse
from eveonline.helpers.corporations.permissions import (
    can_edit_corporation_settings,
)
from eveonline.models import EveCorporation
from eveonline.tasks.corporations import update_corporation

PATH = "corporations/{corporation_id}/refresh"
METHOD = "post"
ROUTE_SPEC = {
    "response": {
        200: CorporationRefreshResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Refresh this corporation from ESI now (CEO and directors)",
}


def post_corporation_refresh(request, corporation_id: int):
    corporation = (
        EveCorporation.objects.select_related("ceo")
        .prefetch_related("directors")
        .filter(corporation_id=corporation_id)
        .first()
    )
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_edit_corporation_settings(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    # The hourly update runs the same task. AppTask drops a copy of the same
    # call that is already queued, so repeated clicks queue one refresh.
    update_corporation.apply_async(args=[corporation.corporation_id])
    return CorporationRefreshResponse(queued=True)
