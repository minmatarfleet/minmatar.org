"""Stable codes for tribe groups (catalog keys for reports and bindings)."""

import re

from django.utils.text import slugify


def make_tribe_group_code(tribe_slug: str, group_name: str) -> str:
    """Build a unique catalog code: ``{tribe_slug}.{group-slug}``."""
    group_part = slugify(group_name) or "group"
    group_part = re.sub(r"[^a-z0-9-]", "", group_part)
    return f"{tribe_slug}.{group_part}"
