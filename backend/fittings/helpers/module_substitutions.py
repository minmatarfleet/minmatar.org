"""Helpers for per-fitting module substitution admin filtering."""

from __future__ import annotations

import re
from collections.abc import Iterable

from django.db.models import Q, QuerySet
from eveuniverse.models import EveType

from market.models.item import parse_eft_items

# Size / capacity tokens that distinguish families within an Eve group
# (e.g. 5MN MWDs vs 50MN MWDs; Medium extenders vs Large).
_SIZE_RE = re.compile(
    r"\b("
    r"\d+\s*MN|"
    r"\d+\s*GJ|"
    r"X-Large|Extra\s*Large|XX-Large|"
    r"Small|Medium|Large|Capital|Micro|Heavy|Civilian|Orbital"
    r")\b",
    re.IGNORECASE,
)

# Words that do not distinguish one module family from another.
_NOISE_WORDS = frozenset(
    {
        "ii",
        "i",
        "iii",
        "compact",
        "enduring",
        "restrained",
        "precise",
        "scoped",
        "limited",
        "ample",
        "focused",
        "modal",
        "gated",
        "anoding",
        "aftiles",
        "quad",
        "lif",
        "type",
        "a",
        "b",
        "c",
        "x",
        "y",
        "t8",
        "t6",
        "t2",
        "the",
        "and",
        "of",
        "mk",
        "mk1",
        "mk2",
        "mk3",
        "mk5",
    }
)

# Shared category nouns: alone they are not enough to call two types variants.
_GENERIC_WORDS = frozenset(
    {
        "laser",
        "missile",
        "launcher",
        "rocket",
        "torpedo",
        "bomb",
        "shield",
        "armor",
        "armour",
        "capacitor",
        "cargo",
        "drone",
        "sensor",
        "warp",
        "ship",
        "module",
    }
)


def fitting_item_names(eft_format: str) -> list[str]:
    """Unique EFT item names excluding the hull (EFT header ship)."""
    items = parse_eft_items(eft_format or "")
    if not items:
        return []
    header_ship = ""
    first_line = (eft_format or "").strip().split("\n", 1)[0]
    if first_line.startswith("["):
        header_ship = first_line.split(",")[0].strip().strip("[]")
    return sorted(name for name in items if name != header_ship)


def fitting_item_types(fitting) -> QuerySet[EveType]:
    """EveTypes present on the fitting's EFT (excluding the hull)."""
    names = fitting_item_names(getattr(fitting, "eft_format", "") or "")
    if not names:
        return EveType.objects.none()
    return EveType.objects.filter(name__in=names, published=True).order_by(
        "name"
    )


def size_token(name: str) -> str | None:
    match = _SIZE_RE.search(name or "")
    if not match:
        return None
    return re.sub(r"\s+", "", match.group(1)).upper()


def family_words(name: str) -> frozenset[str]:
    cleaned = _SIZE_RE.sub(" ", name or "")
    cleaned = re.sub(r"[^a-zA-Z\s]", " ", cleaned)
    words = []
    for raw in cleaned.lower().split():
        if raw in _NOISE_WORDS or len(raw) < 2:
            continue
        words.append(raw)
    return frozenset(words)


def types_are_variants(preferred: EveType, candidate: EveType) -> bool:
    """True when candidate is a meta/faction/T1–T2 sibling of preferred."""
    if preferred.pk == candidate.pk:
        return False
    if preferred.eve_group_id != candidate.eve_group_id:
        return False
    if size_token(preferred.name) != size_token(candidate.name):
        return False
    preferred_words = family_words(preferred.name)
    candidate_words = family_words(candidate.name)
    if not preferred_words or not candidate_words:
        return False
    distinctive_preferred = preferred_words - _GENERIC_WORDS
    distinctive_candidate = candidate_words - _GENERIC_WORDS
    if distinctive_preferred or distinctive_candidate:
        return bool(distinctive_preferred & distinctive_candidate)
    return bool(preferred_words & candidate_words)


def variant_types_for(eve_type: EveType) -> QuerySet[EveType]:
    """Published types in the same group that look like variants of eve_type."""
    if not eve_type or not eve_type.eve_group_id:
        return EveType.objects.none()
    candidates = EveType.objects.filter(
        eve_group_id=eve_type.eve_group_id,
        published=True,
    ).exclude(pk=eve_type.pk)
    size = size_token(eve_type.name)
    if size:
        # \b5MN\b must not match 50MN; allow optional space between digits and MN/GJ.
        if size.endswith("MN"):
            digits = size[:-2]
            pattern = rf"(?i)\b{re.escape(digits)}\s*MN\b"
        elif size.endswith("GJ"):
            digits = size[:-2]
            pattern = rf"(?i)\b{re.escape(digits)}\s*GJ\b"
        else:
            pattern = rf"(?i)\b{re.escape(size)}\b"
        candidates = candidates.filter(name__regex=pattern)

    preferred_words = family_words(eve_type.name)
    distinctive = preferred_words - _GENERIC_WORDS
    match_words = distinctive or preferred_words
    if not match_words:
        return EveType.objects.none()

    name_q = Q()
    for word in match_words:
        name_q |= Q(name__icontains=word)
    candidates = candidates.filter(name_q)

    matching_ids = [
        row.pk
        for row in candidates.only("id", "name", "eve_group_id")
        if types_are_variants(eve_type, row)
    ]
    if not matching_ids:
        return EveType.objects.none()
    return EveType.objects.filter(pk__in=matching_ids).order_by("name")


def variant_types_for_fitting_items(
    fit_types: Iterable[EveType],
) -> QuerySet[EveType]:
    """Union of variants for every type on the fitting (for new-row dropdowns)."""
    fit_list = list(fit_types)
    if not fit_list:
        return EveType.objects.none()
    ids: set[int] = set()
    for eve_type in fit_list:
        ids.update(variant_types_for(eve_type).values_list("pk", flat=True))
    if not ids:
        return EveType.objects.none()
    return EveType.objects.filter(pk__in=ids).order_by("name")
