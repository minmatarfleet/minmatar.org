"""GET /corporations/{corporation_id}/page_text - the headline and sections
on the corporation page, for the CEO and directors to edit."""

from authentication import AuthBearer
from eveonline.endpoints.corporations.schemas import (
    CorporationPageText,
    CorporationPageTextError,
)
from eveonline.helpers.corporations.page_text import (
    editable_corporation,
    page_text,
)

PATH = "corporations/{corporation_id}/page_text"
METHOD = "get"
ROUTE_SPEC = {
    "response": {
        200: CorporationPageText,
        403: CorporationPageTextError,
        404: CorporationPageTextError,
    },
    "auth": AuthBearer(),
    "summary": "The corporation page's headline and sections (CEO and directors)",
}


def get_corporation_page_text(request, corporation_id: int):
    corporation, error = editable_corporation(request.user, corporation_id)
    if error:
        return error
    return page_text(corporation)
