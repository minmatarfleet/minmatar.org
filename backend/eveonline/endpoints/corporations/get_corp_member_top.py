"""GET /corporations/{corporation_id}/members/top - ranked members."""

from ninja import Router

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.corporations.get_corp_member_details import (
    corporation_members,
    member_details,
)
from eveonline.endpoints.corporations.schemas import (
    CorporationMembersTopResponse,
)
from eveonline.helpers.corporations.permissions import (
    can_view_corporation_members,
    can_view_member_characters,
)
from eveonline.helpers.corporations.profile import load_corporation
from eveonline.helpers.corporations.stats_cache import corporation_stats
from timezones.brackets import BRACKET_CODES

router = Router(tags=["Corporations"])

METRICS = ("fleets", "kills", "voice", "timezone")


@router.get(
    "corporations/{corporation_id}/members/top",
    response={
        200: CorporationMembersTopResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Top corporation members by activity",
)
def get_corp_member_top(
    request,
    corporation_id: int,
    metric: str = "fleets",
    limit: int = 10,
):
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_view_corporation_members(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    if metric not in METRICS:
        metric = "fleets"
    limit = max(1, min(limit, 50))
    rows = member_details(
        corporation_members(corporation),
        reveal_characters=can_view_member_characters(
            request.user, corporation
        ),
        stats=corporation_stats(corporation.corporation_id),
    )
    ranked = sort_member_rows(rows, metric)
    return {"metric": metric, "members": ranked[:limit]}


def sort_member_rows(ranked, metric: str):
    rows = list(ranked)
    if metric == "timezone":
        rows.sort(key=_timezone_sort_key)
    else:
        rows.sort(key=lambda row: _sort_key(row, metric), reverse=True)
    return rows


_BRACKET_ORDER = {code: index for index, code in enumerate(BRACKET_CODES)}


def _timezone_sort_key(row):
    """Bracket order (USTZ first), then no timezone yet, then by name."""
    rank = min(
        (
            _BRACKET_ORDER.get(code, len(BRACKET_CODES))
            for code in row.timezone.brackets
        ),
        default=len(BRACKET_CODES) + 1,
    )
    return (rank, row.character_name)


def _sort_key(row, metric: str):
    if metric == "kills":
        return (row.kills_90d, row.fleets_90d, row.character_name)
    if metric == "voice":
        return (row.voice_hours_90d, row.fleets_90d, row.character_name)
    return (row.fleets_90d, row.kills_90d, row.character_name)
