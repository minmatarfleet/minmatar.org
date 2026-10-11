"""GET /corporations/by-slug/{slug} - resolve a page slug to a corporation."""

from ninja import Router

from app.errors import ErrorResponse
from eveonline.endpoints.corporations.schemas import CorporationSlugResponse
from eveonline.helpers.corporations.slugs import (
    corporation_for_slug,
    corporation_slug,
)

router = Router(tags=["Corporations"])


@router.get(
    "corporations/by-slug/{slug}",
    response={200: CorporationSlugResponse, 404: ErrorResponse},
    summary="Resolve a corporation page slug",
)
def get_corporation_by_slug(request, slug: str):
    corporation = corporation_for_slug(slug)
    if corporation is None:
        return 404, {"detail": "Corporation not found"}
    return {
        "corporation_id": corporation.corporation_id,
        "slug": corporation_slug(corporation.name),
    }
