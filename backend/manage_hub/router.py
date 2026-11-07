"""The Manage hub API (mounted at /api/manage/)."""

from datetime import datetime
from typing import Optional

from ninja import Router, Schema

from app.errors import ErrorResponse
from authentication import AuthBearer
from manage_hub import search as entity_search
from manage_hub.screens import can_reach_any
from manage_hub.summary import manage_summary

router = Router(tags=["Manage"])


class ManageQueueResponse(Schema):
    key: str
    # The screen key the queue is worked on.
    screen: str
    count: int
    oldest_at: Optional[datetime] = None
    # The first item to look at: a doctrine, corporation, payout code or feed.
    next_label: str = ""
    # "warn" when any count is a problem (failing feeds), else "".
    tone: str = ""


class ManageScreenResponse(Schema):
    key: str
    group: str


class ManageSummaryResponse(Schema):
    # "superuser" or "manager".
    role: str
    screens: list[ManageScreenResponse]
    queues: list[ManageQueueResponse]
    # Sum of the queue counts (the Neocom badge).
    total: int


class ManageEntityMatchResponse(Schema):
    id: str
    name: str
    detail: str = ""
    icon_url: Optional[str] = None


@router.get(
    "/summary",
    response={200: ManageSummaryResponse},
    auth=AuthBearer(),
    summary="The manage screens the user can reach and what waits on them",
)
def get_summary(request):
    return manage_summary(request.user)


@router.get(
    "/search",
    response={
        200: list[ManageEntityMatchResponse],
        400: ErrorResponse,
        403: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Find a system, corporation, alliance, type, ship, location, "
    "character or Discord channel by name",
)
def get_search(request, kind: str, q: str = ""):
    if kind not in entity_search.KINDS:
        return 400, ErrorResponse(
            detail=f"kind must be one of {', '.join(entity_search.KINDS)}"
        )
    if kind in entity_search.MANAGER_KINDS and not can_reach_any(request.user):
        return 403, ErrorResponse(detail="Only managers can search this.")
    return 200, entity_search.search(request.user, kind, q)
