"""Stable codes for tribe groups (catalog keys for reports and bindings)."""

import re

from django.utils.text import slugify


def make_tribe_group_code(tribe_slug: str, group_name: str) -> str:
    """Build a unique catalog code: ``{tribe_slug}.{group-slug}``."""
    group_part = slugify(group_name) or "group"
    group_part = re.sub(r"[^a-z0-9-]", "", group_part)
    return f"{tribe_slug}.{group_part}"


def ensure_unique_tribe_group_code(tribe_group) -> str:
    """
    Set ``tribe_group.code`` when empty, avoiding collisions (migration 0021 logic).
    """
    if tribe_group.code:
        return tribe_group.code

    # pylint: disable=import-outside-toplevel
    from tribes.models import Tribe, TribeGroup

    tribe_slug = tribe_group.tribe.slug if tribe_group.tribe_id else ""
    if not tribe_slug and tribe_group.tribe_id:
        tribe_slug = (
            Tribe.objects.filter(pk=tribe_group.tribe_id)
            .values_list("slug", flat=True)
            .first()
            or "tribe"
        )

    base = make_tribe_group_code(tribe_slug, tribe_group.name)
    code = base
    suffix = 2
    while True:
        qs = TribeGroup.objects.filter(code=code)
        if tribe_group.pk:
            qs = qs.exclude(pk=tribe_group.pk)
        if not qs.exists():
            break
        code = f"{base}-{suffix}"
        suffix += 1

    tribe_group.code = code
    return code
