"""GET /{page_key} — reading status for the caller's page/version."""

from typing import Optional

from ninja import Schema
from pydantic import Field

from authentication import AuthBearer
from page_progress.helpers import (
    get_read_section_ids,
    parse_section_ids,
    progress_percent,
)
from page_progress.models import UserPageProgress


class PageProgressStatusResponse(Schema):
    page_key: str
    version: Optional[str] = Field(default=None)
    page_title: str = ""
    read_sections: list[str]
    missing_sections: list[str]
    read_count: int
    section_total: int
    percent: int
    is_acknowledged: bool


# path converter allows page_key values like "guides/bookmarks".
PATH = "{path:page_key}"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Page progress status for the authenticated user.",
    "auth": AuthBearer(),
    "response": {200: PageProgressStatusResponse},
}


def get_page_progress(
    request,
    page_key: str,
    version: str = "",
    sections: str = "",
):
    section_ids = parse_section_ids(sections)
    progress = None
    if version:
        progress = UserPageProgress.objects.filter(
            user=request.user,
            page_key=page_key,
            version=version,
        ).first()

    effective_version = version or (progress.version if progress else "")
    read_sections = (
        sorted(
            get_read_section_ids(
                request.user.pk,
                page_key,
                effective_version,
            )
        )
        if effective_version
        else []
    )

    if section_ids:
        missing_sections = [
            section_id
            for section_id in section_ids
            if section_id not in set(read_sections)
        ]
        section_total = len(section_ids)
        read_count = section_total - len(missing_sections)
    else:
        missing_sections = []
        section_total = progress.section_total if progress is not None else 0
        read_count = len(read_sections)

    return PageProgressStatusResponse(
        page_key=page_key,
        version=effective_version or None,
        page_title=progress.page_title if progress is not None else "",
        read_sections=read_sections,
        missing_sections=missing_sections,
        read_count=read_count,
        section_total=section_total,
        percent=progress_percent(read_count, section_total),
        is_acknowledged=(
            progress.is_acknowledged if progress is not None else False
        ),
    )
