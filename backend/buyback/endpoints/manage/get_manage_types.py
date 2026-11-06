"""GET /manage/types - search item types by name."""

from typing import List

from authentication import AuthBearer
from app.errors import ErrorResponse
from buyback.endpoints.manage.common import TypeRow, can_manage, forbidden
from market.helpers.type_search import search_types

PATH = "/manage/types"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Search item types for the accepted-items editor",
    "auth": AuthBearer(),
    "response": {200: List[TypeRow], 403: ErrorResponse},
}


def get_manage_types(request, q: str = ""):
    if not can_manage(request.user):
        return forbidden()
    return 200, [TypeRow(type_id=t.id, name=t.name) for t in search_types(q)]
