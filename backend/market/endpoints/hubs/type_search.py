"""type_search"""

from app.errors import ErrorResponse
from authentication import AuthBearer
from market.helpers.type_search import search_types
from market.endpoints.hubs.common import (
    allowed,
    forbidden,
)
from market.endpoints.hubs.schemas import (
    TypeSearchRow,
)

PATH = "/hubs-type-search"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Search item types by name",
    "auth": AuthBearer(),
    "response": {200: list[TypeSearchRow], 403: ErrorResponse},
}


def type_search(request, q: str = ""):
    if not allowed(request):
        return forbidden()
    return 200, [
        TypeSearchRow(type_id=t.id, name=t.name) for t in search_types(q)
    ]
