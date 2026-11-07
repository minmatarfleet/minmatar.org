"""PUT /corporations/{corporation_id}/page_text - edit the headline and
sections on the corporation page (CEO and directors)."""

from authentication import AuthBearer
from eveonline.endpoints.corporations.schemas import (
    CorporationPageText,
    CorporationPageTextError,
    CorporationPageTextUpdate,
)
from eveonline.helpers.corporations.page_text import (
    PageTextError,
    editable_corporation,
    page_text,
    save_page_text,
)

PATH = "corporations/{corporation_id}/page_text"
METHOD = "put"
ROUTE_SPEC = {
    "response": {
        200: CorporationPageText,
        400: CorporationPageTextError,
        403: CorporationPageTextError,
        404: CorporationPageTextError,
    },
    "auth": AuthBearer(),
    "summary": "Edit the corporation page's headline and sections; profanity is refused (CEO and directors)",
}


def put_corporation_page_text(
    request, corporation_id: int, payload: CorporationPageTextUpdate
):
    corporation, error = editable_corporation(request.user, corporation_id)
    if error:
        return error
    try:
        save_page_text(corporation, payload.dict())
    except PageTextError as e:
        return 400, {"detail": e.code, "field": e.field, "words": e.words}
    return page_text(corporation)
