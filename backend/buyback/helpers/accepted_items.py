"""Buyback accepted-item allowlist helpers and seed."""

from __future__ import annotations

import re
from datetime import timedelta
from decimal import Decimal
from typing import Iterable

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
from industry.helpers.type_breakdown import (
    get_breakdown_for_industry_product,
    type_ids_in_breakdown,
)
from industry.models import IndustryOrder

# Compressed belt/moon ores accepted for buyback. Highsec bases plus selected
# lowsec/nullsec ores (isogen-bearing and Equinox) requested for alliance take.
BUYBACK_ORE_BASES = frozenset(
    {
        # Highsec belt + HS moon
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
        # Lowsec / nullsec belt (incl. isogen-rich)
        "Hedbergite",
        "Hemorphite",
        "Jaspet",
        "Gneiss",
        "Crokite",
        "Dark Ochre",
        # Equinox nullsec
        "Mordunium",
        "Ytirium",
        "Eifyrium",
        "Ducinium",
        "Griemeer",
    }
)

# Back-compat alias for older imports / docs.
HIGHSEC_ORE_BASES = BUYBACK_ORE_BASES

_GRADE_SUFFIX_RE = re.compile(r"\s+(II|III|IV)-Grade$")
_MOON_PREFIX_RE = re.compile(r"^(Brimful|Glistening)\s+")

# Jita ore-buy clamp uses the liquid base type, then these CCP variant factors.
_ORE_GRADE_BUY_FACTORS = {"II": 1.05, "III": 1.10, "IV": 1.15}
_ORE_MOON_BUY_FACTORS = {"Brimful": 1.15, "Glistening": 2.0}

P1_P2_GROUPS = frozenset({GROUP_P1, GROUP_P2})
P3_P4_GROUPS = frozenset({GROUP_P3, GROUP_P4})
DEFAULT_PI_LOOKBACK_DAYS = 90
PI_CATEGORIES = (
    BuybackAcceptedItem.Category.P1,
    BuybackAcceptedItem.Category.P2,
    BuybackAcceptedItem.Category.P3,
    BuybackAcceptedItem.Category.P4,
)


def compressed_buyback_ore_base(name: str) -> str | None:
    """Return the ore base name if this is a matching Compressed buyback type."""
    if not name.startswith("Compressed "):
        return None
    rest = name[len("Compressed ") :]
    rest = _GRADE_SUFFIX_RE.sub("", rest)
    rest = _MOON_PREFIX_RE.sub("", rest)
    if rest in BUYBACK_ORE_BASES:
        return rest
    return None


def compressed_ore_buy_market_name(name: str) -> str | None:
    """Compressed base type whose Jita buy is used for the ore-side clamp."""
    base = compressed_buyback_ore_base(name)
    if not base:
        return None
    return f"Compressed {base}"


def compressed_ore_buy_factor(name: str) -> float:
    """Scale base-ore Jita buy for II/III/IV-Grade and moon prefixes."""
    rest = (
        name[len("Compressed ") :] if name.startswith("Compressed ") else name
    )
    grade = _GRADE_SUFFIX_RE.search(rest)
    if grade:
        return _ORE_GRADE_BUY_FACTORS[grade.group(1)]
    moon = _MOON_PREFIX_RE.match(rest)
    if moon:
        return _ORE_MOON_BUY_FACTORS[moon.group(1)]
    return 1.0


def ore_jita_buy_unit(
    name: str, buy_by_name: dict[str, Decimal]
) -> Decimal | None:
    """Per-unit Jita buy for an ore stack (base type × variant factor)."""
    market_name = compressed_ore_buy_market_name(name)
    if not market_name:
        return None
    base_buy = buy_by_name.get(market_name)
    if base_buy is None:
        return None
    return base_buy * Decimal(str(compressed_ore_buy_factor(name)))


# Back-compat alias.
compressed_highsec_base = compressed_buyback_ore_base


def category_for_eve_type(eve_type: EveType) -> str | None:
    """Map an EveType to a BuybackAcceptedItem.Category value, or None."""
    if compressed_buyback_ore_base(eve_type.name):
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


def pi_type_ids_from_recent_orders(
    *, lookback_days: int = DEFAULT_PI_LOOKBACK_DAYS
) -> set[int]:
    """
    Distinct P3–P4 type IDs appearing in BOMs of industry orders created in
    the lookback window.

    All published P1/P2 are seeded via ``iter_seed_all_p1_p2_eve_types``.
    """
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
                material_ids.update(type_ids_in_breakdown(tree))
    except Exception:
        # Industry tables may not exist yet during early buyback migrations.
        return set()

    if not material_ids:
        return set()

    return set(
        EveType.objects.filter(
            id__in=material_ids,
            eve_group_id__in=P3_P4_GROUPS,
            published=True,
        ).values_list("id", flat=True)
    )


def iter_seed_ore_eve_types() -> Iterable[EveType]:
    for eve_type in (
        EveType.objects.filter(published=True, name__startswith="Compressed ")
        .select_related("eve_group")
        .iterator()
    ):
        if compressed_buyback_ore_base(eve_type.name):
            yield eve_type


def iter_seed_all_p1_p2_eve_types() -> Iterable[EveType]:
    """All published P1 and P2 planetary commodities (surplus unless in demand)."""
    yield from (
        EveType.objects.filter(
            published=True,
            eve_group_id__in=P1_P2_GROUPS,
        )
        .select_related("eve_group")
        .order_by("name")
        .iterator()
    )


def iter_seed_p3_p4_eve_types(
    *, lookback_days: int = DEFAULT_PI_LOOKBACK_DAYS
) -> Iterable[EveType]:
    """P3/P4 types that appear in recent industry-order BOMs."""
    type_ids = pi_type_ids_from_recent_orders(lookback_days=lookback_days)
    if not type_ids:
        return
    yield from (
        EveType.objects.filter(id__in=type_ids)
        .select_related("eve_group")
        .order_by("name")
        .iterator()
    )


# Back-compat alias.
iter_seed_pi_eve_types = iter_seed_p3_p4_eve_types


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
    Upsert compressed buyback ores, all published P1/P2, and P3/P4 used in
    recent industry orders.

    Full P1/P2 stay on the allowlist (surplus rate unless in supply-chain
    demand). P3/P4 outside the lookback BOM set are deactivated. When
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

    for eve_type in iter_seed_all_p1_p2_eve_types():
        result = _upsert_accepted(eve_type, seed_ids)
        pi_seed_ids.add(eve_type.id)
        if result == "created":
            created += 1
        elif result == "updated":
            updated += 1

    for eve_type in iter_seed_p3_p4_eve_types(lookback_days=pi_lookback_days):
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
