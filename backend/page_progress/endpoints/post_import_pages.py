"""POST /import — merge anonymous/local progress into the authenticated user."""

from ninja import Schema

from app.errors import ErrorResponse
from authentication import AuthBearer
from page_progress.helpers import (
    MAX_IMPORT_PAGES,
    MAX_SECTIONS_PER_IMPORT_PAGE,
    import_page_progress,
    progress_percent,
)

PATH = "import"
METHOD = "post"
ROUTE_SPEC = {
    "summary": (
        "Union-merge client-side (anonymous) page progress into the "
        "authenticated user's records."
    ),
    "auth": AuthBearer(),
}


class ImportPagePayload(Schema):
    page_key: str
    version: str
    page_title: str = ""
    section_total: int = 0
    read_sections: list[str] = []
    is_acknowledged: bool = False


class ImportPagesRequest(Schema):
    pages: list[ImportPagePayload]


class ImportedPageResult(Schema):
    page_key: str
    version: str
    read_count: int
    section_total: int
    percent: int
    is_acknowledged: bool


class ImportPagesResponse(Schema):
    imported: list[ImportedPageResult]
    skipped: int = 0


ROUTE_SPEC["response"] = {
    200: ImportPagesResponse,
    400: ErrorResponse,
}


def post_import_pages(request, payload: ImportPagesRequest):
    pages = payload.pages or []
    if len(pages) > MAX_IMPORT_PAGES:
        return 400, ErrorResponse(
            detail=f"At most {MAX_IMPORT_PAGES} pages per import.",
        )

    imported: list[ImportedPageResult] = []
    skipped = 0

    for page in pages:
        page_key = (page.page_key or "").strip()
        version = (page.version or "").strip()
        if not page_key or not version:
            skipped += 1
            continue

        read_sections = (page.read_sections or [])[
            :MAX_SECTIONS_PER_IMPORT_PAGE
        ]
        if page.section_total < 0:
            skipped += 1
            continue

        try:
            progress = import_page_progress(
                user=request.user,
                page_key=page_key,
                version=version,
                page_title=(page.page_title or "").strip(),
                section_total=page.section_total,
                read_sections=read_sections,
                is_acknowledged=bool(page.is_acknowledged),
            )
        except ValueError:
            skipped += 1
            continue

        read_count = progress.read_count
        imported.append(
            ImportedPageResult(
                page_key=page_key,
                version=version,
                read_count=read_count,
                section_total=progress.section_total,
                percent=progress_percent(read_count, progress.section_total),
                is_acknowledged=progress.is_acknowledged,
            )
        )

    return ImportPagesResponse(imported=imported, skipped=skipped)
