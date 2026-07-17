"""Shared helpers for page progress endpoints and admin."""

from django.utils import timezone

from page_progress.models import UserPageProgress, UserPageSectionProgress


def parse_section_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for part in raw.split(","):
        section_id = part.strip()
        if not section_id or section_id in seen:
            continue
        seen.add(section_id)
        result.append(section_id)
    return result


def get_read_section_ids(
    user_id: int,
    page_key: str,
    version: str,
) -> set[str]:
    return set(
        UserPageSectionProgress.objects.filter(
            user_id=user_id,
            page_key=page_key,
            version=version,
        ).values_list("section_id", flat=True)
    )


def progress_percent(read_count: int, section_total: int) -> int:
    if section_total <= 0:
        return 0
    return round(100 * read_count / section_total)


def ensure_page_progress(
    *,
    user,
    page_key: str,
    version: str,
    page_title: str = "",
    section_total: int | None = None,
) -> UserPageProgress:
    defaults: dict = {}
    if page_title:
        defaults["page_title"] = page_title
    if section_total is not None:
        defaults["section_total"] = section_total

    progress, created = UserPageProgress.objects.get_or_create(
        user=user,
        page_key=page_key,
        version=version,
        defaults=defaults,
    )
    if created:
        return progress

    update_fields: list[str] = ["last_seen_at"]
    if page_title and progress.page_title != page_title:
        progress.page_title = page_title
        update_fields.append("page_title")
    if section_total is not None and progress.section_total != section_total:
        progress.section_total = section_total
        update_fields.append("section_total")
    progress.last_seen_at = timezone.now()
    progress.save(update_fields=update_fields)
    return progress


def mark_section_read(
    *,
    user,
    page_key: str,
    section_id: str,
    version: str,
    page_title: str = "",
    section_total: int | None = None,
) -> tuple[UserPageProgress, UserPageSectionProgress, bool]:
    progress = ensure_page_progress(
        user=user,
        page_key=page_key,
        version=version,
        page_title=page_title,
        section_total=section_total,
    )
    section, created = UserPageSectionProgress.objects.get_or_create(
        user=user,
        page_key=page_key,
        section_id=section_id,
        version=version,
    )
    if not created:
        section.last_seen_at = timezone.now()
        section.save(update_fields=["last_seen_at"])
        progress.last_seen_at = timezone.now()
        progress.save(update_fields=["last_seen_at"])
    return progress, section, created


MAX_IMPORT_PAGES = 50
MAX_SECTIONS_PER_IMPORT_PAGE = 200


def import_page_progress(
    *,
    user,
    page_key: str,
    version: str,
    page_title: str = "",
    section_total: int = 0,
    read_sections: list[str] | None = None,
    is_acknowledged: bool = False,
) -> UserPageProgress:
    """
    Union-merge anonymous (or bulk) progress into the authenticated user's rows.
    Never deletes existing server sections.
    """
    version = (version or "").strip()
    page_key = (page_key or "").strip()
    if not version or not page_key:
        raise ValueError("page_key and version are required.")

    seen: set[str] = set()
    sections: list[str] = []
    for section_id in read_sections or []:
        cleaned = (section_id or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        sections.append(cleaned)
        if len(sections) >= MAX_SECTIONS_PER_IMPORT_PAGE:
            break

    progress = ensure_page_progress(
        user=user,
        page_key=page_key,
        version=version,
        page_title=(page_title or "").strip(),
        section_total=max(section_total, 0),
    )

    if section_total > progress.section_total:
        progress.section_total = section_total
        progress.save(update_fields=["section_total", "last_seen_at"])

    for section_id in sections:
        mark_section_read(
            user=user,
            page_key=page_key,
            section_id=section_id,
            version=version,
            page_title=(page_title or "").strip(),
            section_total=progress.section_total,
        )

    if is_acknowledged and not progress.is_acknowledged:
        progress.acknowledged_at = timezone.now()
        progress.save(update_fields=["acknowledged_at", "last_seen_at"])

    # Refresh from DB for accurate read_count after marks.
    progress.refresh_from_db()
    return progress
