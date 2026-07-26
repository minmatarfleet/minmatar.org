"""POST /{page_key}/ack — acknowledge a page after all sections are read."""

from django.utils import timezone
from ninja import Schema

from app.errors import ErrorResponse
from authentication import AuthBearer
from page_progress.helpers import (
    ensure_page_progress,
    get_read_section_ids,
    progress_percent,
)

PATH = "{path:page_key}/ack"
METHOD = "post"
ROUTE_SPEC = {
    "summary": (
        "Acknowledge the current page content after all sections are read."
    ),
    "auth": AuthBearer(),
}


class PageAckRequest(Schema):
    version: str
    sections: list[str]
    page_title: str = ""


class PageAckResponse(Schema):
    page_key: str
    version: str
    read_count: int
    section_total: int
    percent: int
    is_acknowledged: bool
    missing_sections: list[str] = []


ROUTE_SPEC["response"] = {
    200: PageAckResponse,
    400: ErrorResponse,
}


def post_page_ack(request, page_key: str, payload: PageAckRequest):
    version = (payload.version or "").strip()
    if not version:
        return 400, ErrorResponse(detail="version is required.")

    # Preserve order while de-duplicating.
    seen: set[str] = set()
    sections: list[str] = []
    for section_id in payload.sections or []:
        cleaned = (section_id or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        sections.append(cleaned)

    if not sections:
        return 400, ErrorResponse(detail="sections is required.")

    read_ids = get_read_section_ids(request.user.pk, page_key, version)
    missing_sections = [
        section_id for section_id in sections if section_id not in read_ids
    ]
    if missing_sections:
        return 400, ErrorResponse(
            detail=(
                "Cannot acknowledge until all sections are read. "
                f"Missing: {', '.join(missing_sections)}"
            ),
        )

    progress = ensure_page_progress(
        user=request.user,
        page_key=page_key,
        version=version,
        page_title=(payload.page_title or "").strip(),
        section_total=len(sections),
    )
    if not progress.is_acknowledged:
        progress.acknowledged_at = timezone.now()
        progress.save(update_fields=["acknowledged_at", "last_seen_at"])

    read_count = len(sections)
    return PageAckResponse(
        page_key=page_key,
        version=version,
        read_count=read_count,
        section_total=len(sections),
        percent=progress_percent(read_count, len(sections)),
        is_acknowledged=True,
        missing_sections=[],
    )
