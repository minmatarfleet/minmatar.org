"""The words on the corporation page that the CEO and directors edit:
headline, About us, Notable participation and How we fly."""

from __future__ import annotations

from app.profanity import find_profanity
from eveonline.helpers.corporations.permissions import (
    can_edit_corporation_settings,
)
from eveonline.models import EveCorporation

FIELDS = ("introduction", "biography", "highlights", "activity_summary")

# The headline is one or two sentences; the rest are Markdown sections.
INTRODUCTION_MAX = 500
TEXT_MAX = 10000


class PageTextError(ValueError):
    def __init__(self, code: str, field: str, words=None):
        super().__init__(code)
        self.code = code
        self.field = field
        self.words = list(words or [])


def editable_corporation(user, corporation_id: int):
    """(corporation, None), or (None, an error response) when it doesn't
    exist or the user isn't its CEO or a director."""
    corporation = EveCorporation.objects.filter(
        corporation_id=corporation_id
    ).first()
    if corporation is None:
        return None, (404, {"detail": "not_found"})
    if not can_edit_corporation_settings(user, corporation):
        return None, (403, {"detail": "not_allowed"})
    return corporation, None


def page_text(corporation: EveCorporation) -> dict:
    return {
        "corporation_id": corporation.corporation_id,
        **{field: getattr(corporation, field) or "" for field in FIELDS},
        "introduction_max": INTRODUCTION_MAX,
        "text_max": TEXT_MAX,
    }


def _limit(field: str) -> int:
    return INTRODUCTION_MAX if field == "introduction" else TEXT_MAX


def save_page_text(corporation: EveCorporation, changes: dict) -> list[str]:
    """Save the given fields (None leaves one alone) and return the names
    of those that changed. Nothing saves if any field is refused: too long
    when it changed, or containing profanity."""
    cleaned = {}
    for field in FIELDS:
        value = changes.get(field)
        if value is None:
            continue
        value = value.strip()
        if field == "introduction":
            # A headline is one line.
            value = " ".join(value.split())
        changed = value != (getattr(corporation, field) or "")
        # Text saved before the limit existed can stay as long as it is.
        if changed and len(value) > _limit(field):
            raise PageTextError("too_long", field)
        words = find_profanity(value)
        if words:
            raise PageTextError("profanity", field, words)
        if changed:
            cleaned[field] = value
    for field, value in cleaned.items():
        setattr(corporation, field, value)
    if cleaned:
        corporation.save(update_fields=[*cleaned, "updated_at"])
    return list(cleaned)
