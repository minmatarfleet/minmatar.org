"""Buyback accepted-item allowlist helpers and seed."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any, Iterable

from django.db import transaction
from django.utils import timezone
from eveuniverse.models import EveType

from buyback.helpers.classify import (
    GROUP_P1,
    GROUP_P2,
    GROUP_P3,
    GROUP_P4,
)
from buyback.models import BuybackAcceptedItem

HIGHSEC_ORE_BASES = frozenset(
    {
        "Veldspar",
        "Scordite",
        "Pyroxeres",
        "Plagioclase",
        "Omber",
        "Kernite",
        "Zeolites",
        "Sylvite",
        "Bitumens",
        "Coesite",
    }
)

_GRADE_SUFFIX_RE = re.compile(r"\s+(II|III|IV)-Grade$")
_MOON_PREFIX_RE = re.compile(r"^(Brimful|Glistening)\s+")

PI_GROUPS = frozenset({GROUP_P1, GROUP_P2, GROUP_P3, GROUP_P4})
DEFAULT_PI_LOOKBACK_DAYS = 90
PI_CATEGORIES = (
    BuybackAcceptedItem.Category.P1,
    BuybackAcceptedItem.Category.P2,
    BuybackAcceptedItem.Category.P3,
    BuybackAcceptedItem.Category.P4,
)


def compressed_highsec_base(name: str) -> str | None:
    """Return the highsec ore base name if this is a matching Compressed type."""
    if not name.startswith("Compressed "):
        return None
    rest = name[len("Compressed ") :]
    rest = _GRADE_SUFFIX_RE.sub("", rest)
    rest = _MOON_PREFIX_RE.sub("", rest)
    if rest in HIGHSEC_ORE_BASES:
        return rest
    return None


def category_for_eve_type(eve_type: EveType) -> str | None:
    """Map an EveType to a BuybackAcceptedItem.Category value, or None."""
    if compressed_highsec_base(eve_type.name):
        return BuybackAcceptedItem.Category.ORE
    group_id = getattr(eve_type, "eve_group_id", None)
    if group_id == GROUP_P1:
        return BuybackAcceptedItem.Category.P1
    if group_id == GROUP_P2:
        return BuybackAcceptedItem.Category.P2
    if group_id == GROUP_P3:
        return BuybackAcceptedItem.Category.P3
    if group_id == GROUP_P4:
        return BuybackAcceptedItem.Category.P4
    return None


def _type_ids_in_breakdown(node: dict[str, Any] | None) -> set[int]:
    """Collect every type_id in a nested industry breakdown tree."""
    if not node:
        return set()
    ids: set[int] = set()
    stack: list[dict[str, Any]] = [node]
    while stack:
        current = stack.pop()
        type_id = current.get("type_id")
        if type_id is not None:
            ids.add(int(type_id))
        stack.extend(current.get("children") or [])
    return ids


def pi_type_ids_from_recent_orders(
    *, lookback_days: int = DEFAULT_PI_LOOKBACK_DAYS
) -> set[int]:
    """
    Distinct P1–P4 type IDs appearing in BOMs of industry orders created in
    the lookback window.
    """
    try:
        # Optional industry dependency for dynamic PI allowlist.
        from industry.helpers.type_breakdown import (  # pylint: disable=import-outside-toplevel
            get_breakdown_for_industry_product,
        )
        from industry.models import (  # pylint: disable=import-outside-toplevel
            IndustryOrder,
        )
    except Exception:
        return set()

    since = timezone.now() - timedelta(days=lookback_days)
    material_ids: set[int] = set()
    try:
        orders = IndustryOrder.objects.filter(
            created_at__gte=since
        ).prefetch_related("items__eve_type")
        for order in orders:
            for item in order.items.all():
                try:
                    tree = get_breakdown_for_industry_product(
                        item.eve_type,
                        item.quantity,
                        store=True,
                    )
                except Exception:
                    continue
                material_ids.update(_type_ids_in_breakdown(tree))
    except Exception:
        # Industry tables may not exist yet during early buyback migrations.
        return set()

    if not material_ids:
        return set()

    return set(
        EveType.objects.filter(
            id__in=material_ids,
            eve_group_id__in=PI_GROUPS,
            published=True,
        ).values_list("id", flat=True)
    )


def iter_seed_ore_eve_types() -> Iterable[EveType]:
    for eve_type in (
        EveType.objects.filter(published=True, name__startswith="Compressed ")
        .select_related("eve_group")
        .iterator()
    ):
        if compressed_highsec_base(eve_type.name):
            yield eve_type


def iter_seed_pi_eve_types(
    *, lookback_days: int = DEFAULT_PI_LOOKBACK_DAYS
) -> Iterable[EveType]:
    type_ids = pi_type_ids_from_recent_orders(lookback_days=lookback_days)
    if not type_ids:
        return
    yield from (
        EveType.objects.filter(id__in=type_ids)
        .select_related("eve_group")
        .order_by("name")
        .iterator()
    )


def get_active_accepted_type_ids() -> set[int]:
    return set(
        BuybackAcceptedItem.objects.filter(active=True).values_list(
            "eve_type_id", flat=True
        )
    )


def _upsert_accepted(eve_type: EveType, seed_ids: set[int]) -> str:
    category = category_for_eve_type(eve_type)
    if category is None:
        return "skipped"
    seed_ids.add(eve_type.id)
    _, was_created = BuybackAcceptedItem.objects.update_or_create(
        eve_type=eve_type,
        defaults={
            "active": True,
            "category": category,
        },
    )
    return "created" if was_created else "updated"


@transaction.atomic
def seed_accepted_items(
    *,
    deactivate_missing: bool = False,
    pi_lookback_days: int = DEFAULT_PI_LOOKBACK_DAYS,
) -> dict[str, int]:
    """
    Upsert compressed highsec ores + PI used in recent industry orders.

    PI rows outside the lookback BOM set are always deactivated. When
    deactivate_missing is True, active ore rows not in the seed set are also
    deactivated.
    """
    created = 0
    updated = 0
    seed_ids: set[int] = set()
    pi_seed_ids: set[int] = set()

    for eve_type in iter_seed_ore_eve_types():
        result = _upsert_accepted(eve_type, seed_ids)
        if result == "created":
            created += 1
        elif result == "updated":
            updated += 1

    for eve_type in iter_seed_pi_eve_types(lookback_days=pi_lookback_days):
        result = _upsert_accepted(eve_type, seed_ids)
        pi_seed_ids.add(eve_type.id)
        if result == "created":
            created += 1
        elif result == "updated":
            updated += 1

    deactivated_pi = (
        BuybackAcceptedItem.objects.filter(
            active=True,
            category__in=PI_CATEGORIES,
        )
        .exclude(eve_type_id__in=pi_seed_ids)
        .update(active=False)
    )

    deactivated_other = 0
    if deactivate_missing and seed_ids:
        deactivated_other = (
            BuybackAcceptedItem.objects.filter(active=True)
            .exclude(eve_type_id__in=seed_ids)
            .exclude(category__in=PI_CATEGORIES)
            .update(active=False)
        )

    return {
        "created": created,
        "updated": updated,
        "seeded": len(seed_ids),
        "pi_seeded": len(pi_seed_ids),
        "deactivated": deactivated_pi + deactivated_other,
        "deactivated_pi": deactivated_pi,
    }
