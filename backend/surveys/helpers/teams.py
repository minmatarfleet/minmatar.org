"""Live tribe rows for the survey, sourced from the tribes app.

Each active tribe becomes a rateable row, carrying its chief's character id and
name so the UI can show the chief's portrait and a hover.
"""

import logging

from tribes.models import Tribe

logger = logging.getLogger(__name__)


def _chief(user) -> tuple[int | None, str]:
    """Return (character_id, character_name) for a tribe chief, best-effort."""
    if not user:
        return None, ""
    try:
        player = getattr(user, "eveplayer", None)
        pc = player.primary_character if player else None
        if pc:
            return pc.character_id, pc.character_name
    except Exception:  # pragma: no cover - defensive
        pass
    return None, getattr(user, "username", "") or ""


def _group_rows(tribe) -> list[dict]:
    """Sub-groups of a tribe, with their chiefs, so raters see the whole tribe."""
    out = []
    try:
        for tg in tribe.groups.all():
            if not getattr(tg, "is_active", True):
                continue
            cid, cname = _chief(tg.chief)
            out.append({"name": tg.name, "chief_id": cid, "chief_name": cname})
        out.sort(key=lambda g: g["name"])
    except Exception:  # pragma: no cover - defensive
        logger.debug("group rows failed", exc_info=True)
    return out


def _row_from_tribe(tribe) -> dict:
    chief_id, chief_name = _chief(tribe.chief)
    return {
        "key": tribe.slug,
        "label": tribe.name,
        "chief_id": chief_id,
        "chief_name": chief_name,
        "hint": f"Chief: {chief_name}" if chief_name else "",
        "groups": _group_rows(tribe),
    }


def tribe_team_rows() -> list[dict]:
    """One row per active tribe (for the ratings matrix), with sub-groups."""
    try:
        return [
            _row_from_tribe(t)
            for t in Tribe.objects.filter(is_active=True)
            .select_related("chief__eveplayer__primary_character")
            .prefetch_related("groups__chief__eveplayer__primary_character")
            .order_by("name")
        ]
    except Exception:  # pragma: no cover - defensive
        logger.exception("tribe_team_rows failed")
        return []


def member_tribe_rows(user) -> list[dict]:
    """The active tribes this user belongs to, with chief info."""
    try:
        memberships = user.tribe_memberships.filter(
            status="active"
        ).select_related(
            "tribe_group__tribe__chief__eveplayer__primary_character"
        )
        seen = set()
        rows = []
        for m in memberships:
            tg = m.tribe_group
            tribe = tg.tribe if tg else None
            if not tribe or tribe.pk in seen:
                continue
            seen.add(tribe.pk)
            rows.append(_row_from_tribe(tribe))
        return rows
    except Exception:  # pragma: no cover - defensive
        logger.debug("member_tribe_rows failed", exc_info=True)
        return []


def resolve_dynamic_rows(row_source: str) -> list[dict]:
    if row_source == "tribes":
        return tribe_team_rows()
    return []
