"""POST /{page_key}/sections/{section_id}/read — mark a section viewed."""

from ninja import Schema

from app.errors import ErrorResponse
from authentication import AuthBearer
from page_progress.helpers import mark_section_read, progress_percent

PATH = "{path:page_key}/sections/{section_id}/read"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Record that the authenticated user viewed a page section.",
    "auth": AuthBearer(),
}


class MarkSectionReadRequest(Schema):
    version: str
    page_title: str = ""
    section_total: int = 0


class MarkSectionReadResponse(Schema):
    page_key: str
    section_id: str
    version: str
    created: bool
    read_count: int
    section_total: int
    percent: int
    is_acknowledged: bool


ROUTE_SPEC["response"] = {
    200: MarkSectionReadResponse,
    400: ErrorResponse,
}


def post_section_read(
    request,
    page_key: str,
    section_id: str,
    payload: MarkSectionReadRequest,
):
    version = (payload.version or "").strip()
    section_id = (section_id or "").strip()
    if not version:
        return 400, ErrorResponse(detail="version is required.")
    if not section_id:
        return 400, ErrorResponse(detail="section_id is required.")
    if payload.section_total < 0:
        return 400, ErrorResponse(
            detail="section_total must be non-negative.",
        )

    progress, _, created = mark_section_read(
        user=request.user,
        page_key=page_key,
        section_id=section_id,
        version=version,
        page_title=(payload.page_title or "").strip(),
        section_total=payload.section_total,
    )
    read_count = progress.read_count
    return MarkSectionReadResponse(
        page_key=page_key,
        section_id=section_id,
        version=version,
        created=created,
        read_count=read_count,
        section_total=progress.section_total,
        percent=progress_percent(read_count, progress.section_total),
        is_acknowledged=progress.is_acknowledged,
    )
