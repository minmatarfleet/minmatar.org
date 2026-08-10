"""Annotate accepted buyback types with used-in products and demand flags."""

from __future__ import annotations

from dataclasses import dataclass

from buyback.helpers.demand import mineral_name_to_id_for_ores
from buyback.models import BuybackAcceptedItem
from industry.helpers.compressed_ore import ore_materials_per_portion
from industry.helpers.type_breakdown import type_ids_in_breakdown
from industry.models import IndustryProduct


@dataclass(frozen=True)
class UsedInProduct:
    type_id: int
    name: str


@dataclass(frozen=True)
class AnnotatedAcceptedItem:
    type_id: int
    name: str
    category: str
    used_in: list[UsedInProduct]
    in_demand: bool
    demand_status: str
    demand_quantity: int
    stockpile_quantity: int


def used_in_by_material_type_id() -> dict[int, list[UsedInProduct]]:
    """Map material type ID → IndustryProducts that use it (by product name)."""
    mapping: dict[int, dict[int, str]] = {}
    for product in IndustryProduct.objects.select_related("eve_type").all():
        breakdown = product.breakdown
        if not breakdown:
            continue
        material_ids = type_ids_in_breakdown(breakdown)
        material_ids.discard(product.eve_type_id)
        product_name = product.eve_type.name
        product_type_id = product.eve_type_id
        for material_id in material_ids:
            mapping.setdefault(material_id, {})[product_type_id] = product_name

    return {
        material_id: [
            UsedInProduct(type_id=type_id, name=name)
            for type_id, name in sorted(
                products_by_id.items(), key=lambda item: item[1].lower()
            )
        ]
        for material_id, products_by_id in mapping.items()
    }


def used_in_for_accepted_type(
    *,
    type_id: int,
    category: str,
    type_name: str,
    material_used_in: dict[int, list[UsedInProduct]],
    mineral_name_to_id: dict[str, int] | None = None,
) -> list[UsedInProduct]:
    """Products using this type (ore: via refined minerals)."""
    if category != BuybackAcceptedItem.Category.ORE:
        return list(material_used_in.get(type_id, []))

    try:
        materials = ore_materials_per_portion(type_name)
    except Exception:
        return list(material_used_in.get(type_id, []))

    if not materials:
        return list(material_used_in.get(type_id, []))

    if mineral_name_to_id is None:
        mineral_name_to_id = mineral_name_to_id_for_ores([type_name])

    by_product: dict[int, str] = {}
    for mineral_name in materials:
        mineral_id = mineral_name_to_id.get(mineral_name)
        if mineral_id is None:
            continue
        for entry in material_used_in.get(mineral_id, []):
            by_product[entry.type_id] = entry.name

    return [
        UsedInProduct(type_id=product_id, name=name)
        for product_id, name in sorted(
            by_product.items(), key=lambda item: item[1].lower()
        )
    ]


def annotate_active_accepted_items() -> list[AnnotatedAcceptedItem]:
    """Active allowlist rows with used_in + stored demand/stockpile metrics."""
    material_used_in = used_in_by_material_type_id()
    active_items = list(
        BuybackAcceptedItem.objects.filter(active=True)
        .select_related("eve_type")
        .order_by("category", "eve_type__name")
    )
    ore_names = [
        item.eve_type.name
        for item in active_items
        if item.category == BuybackAcceptedItem.Category.ORE
    ]
    mineral_name_to_id = mineral_name_to_id_for_ores(ore_names)

    annotated: list[AnnotatedAcceptedItem] = []
    for item in active_items:
        annotated.append(
            AnnotatedAcceptedItem(
                type_id=item.eve_type_id,
                name=item.eve_type.name,
                category=item.category,
                used_in=used_in_for_accepted_type(
                    type_id=item.eve_type_id,
                    category=item.category,
                    type_name=item.eve_type.name,
                    material_used_in=material_used_in,
                    mineral_name_to_id=mineral_name_to_id,
                ),
                in_demand=item.in_demand,
                demand_status=item.demand_status,
                demand_quantity=int(item.demand_quantity or 0),
                stockpile_quantity=int(item.stockpile_quantity or 0),
            )
        )
    return annotated
