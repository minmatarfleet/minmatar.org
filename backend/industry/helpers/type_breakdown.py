"""
Break down an EveType into its components using the eveuniverse data model.

Components come from: EveTypeMaterial (e.g. reprocessing), blueprint
manufacturing (activity_id=1), or reactions (activity_id=11). Components
that are themselves built from blueprints/reactions are expanded recursively.

Blueprint/reaction data is loaded from the SDE on demand when breaking down
a product type (e.g. a ship).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from eveuniverse.models import (
    EveIndustryActivityMaterial,
    EveIndustryActivityProduct,
    EveType,
    EveTypeMaterial,
)

ACTIVITY_MANUFACTURING = 1
ACTIVITY_REACTION = 11


def _ensure_industry_data_loaded_for_product(
    product_eve_type: EveType,
) -> None:
    """Load blueprint/reaction industry data from SDE if this type is a product."""
    if EveIndustryActivityProduct.objects.filter(
        product_eve_type_id=product_eve_type.id,
        activity_id__in=(ACTIVITY_MANUFACTURING, ACTIVITY_REACTION),
    ).exists():
        return
    try:
        data_all = (
            EveIndustryActivityProduct.objects._fetch_sde_data_cached()
        )  # pylint: disable=protected-access
    except Exception:
        return
    product_id = product_eve_type.id
    for blueprint_type_id, products_list in data_all.items():
        for row in products_list:
            try:
                if int(row.get("productTypeID")) != product_id:
                    continue
                if int(row.get("activityID")) not in (
                    ACTIVITY_MANUFACTURING,
                    ACTIVITY_REACTION,
                ):
                    continue
            except (TypeError, ValueError):
                continue
            EveType.objects.get_or_create_esi(
                id=blueprint_type_id,
                enabled_sections=[EveType.Section.INDUSTRY_ACTIVITIES],
            )
            return


@dataclass
class ComponentNode:
    """One node in the breakdown tree."""

    eve_type: EveType
    quantity: int
    source: str
    depth: int
    children: List["ComponentNode"] = field(default_factory=list)

    def __str__(self) -> str:
        return f"{self.eve_type.name} x{self.quantity} ({self.source})"


def _get_blueprint_or_reaction_materials(
    product_eve_type: EveType,
) -> Optional[Tuple[EveType, int, str, int]]:
    """Return (blueprint_type, activity_id, source_label, product_quantity) or None.
    product_quantity is output units per run (1 for manufacturing, often >1 for reactions).
    """
    _ensure_industry_data_loaded_for_product(product_eve_type)
    products = EveIndustryActivityProduct.objects.filter(
        product_eve_type_id=product_eve_type.id,
        activity_id__in=(ACTIVITY_MANUFACTURING, ACTIVITY_REACTION),
    ).select_related("eve_type", "activity")

    for prod in products:
        product_qty = prod.quantity or 1
        if prod.activity_id == ACTIVITY_MANUFACTURING:
            return (
                prod.eve_type,
                ACTIVITY_MANUFACTURING,
                "blueprint",
                product_qty,
            )
        if prod.activity_id == ACTIVITY_REACTION:
            return (prod.eve_type, ACTIVITY_REACTION, "reaction", product_qty)
    return None


def _get_direct_components(
    eve_type: EveType,
) -> List[Tuple[EveType, int, str, int]]:
    """Direct components as (EveType, quantity_per_run, source, product_quantity).
    product_quantity: output units per run for this recipe (1 for manufacturing/type_material).
    """
    result: List[Tuple[EveType, int, str, int]] = []

    blueprint_or_reaction = _get_blueprint_or_reaction_materials(eve_type)
    if blueprint_or_reaction is not None:
        source_type, activity_id, source_label, product_qty = (
            blueprint_or_reaction
        )
        materials = EveIndustryActivityMaterial.objects.filter(
            eve_type_id=source_type.id,
            activity_id=activity_id,
        ).select_related("material_eve_type")
        for m in materials:
            result.append(
                (m.material_eve_type, m.quantity, source_label, product_qty)
            )
        return result

    for m in EveTypeMaterial.objects.filter(
        eve_type_id=eve_type.id
    ).select_related("material_eve_type"):
        result.append((m.material_eve_type, m.quantity, "type_material", 1))
    return result


def break_down_type(
    eve_type: EveType,
    quantity: int = 1,
    depth: int = 0,
    visited: Optional[Set[int]] = None,
    max_depth: Optional[int] = None,
) -> ComponentNode:
    """Recursively break down a type into a tree of ComponentNodes."""
    if visited is None:
        visited = set()

    direct = _get_direct_components(eve_type)
    if not direct:
        return ComponentNode(
            eve_type=eve_type,
            quantity=quantity,
            source="raw",
            depth=depth,
            children=[],
        )

    stop_deeper = max_depth is not None and depth >= max_depth
    children: List[ComponentNode] = []
    seen = visited | {eve_type.id}

    for material_type, q_per_run, source, product_qty in direct:
        runs = (
            ((quantity + product_qty - 1) // product_qty)
            if product_qty
            else quantity
        )
        total_q = q_per_run * runs
        if stop_deeper or material_type.id in seen:
            children.append(
                ComponentNode(
                    eve_type=material_type,
                    quantity=total_q,
                    source=source,
                    depth=depth + 1,
                    children=[],
                )
            )
            continue
        child_has_breakdown = (
            _get_blueprint_or_reaction_materials(material_type) is not None
            or EveTypeMaterial.objects.filter(eve_type=material_type).exists()
        )
        if child_has_breakdown:
            child_node = break_down_type(
                material_type,
                quantity=total_q,
                depth=depth + 1,
                visited=seen | {material_type.id},
                max_depth=max_depth,
            )
            child_node.source = source
            child_node.quantity = total_q
            children.append(child_node)
        else:
            children.append(
                ComponentNode(
                    eve_type=material_type,
                    quantity=total_q,
                    source=source,
                    depth=depth + 1,
                    children=[],
                )
            )
        seen = seen | {material_type.id}

    return ComponentNode(
        eve_type=eve_type,
        quantity=quantity,
        source="raw" if depth == 0 else "composite",
        depth=depth,
        children=children,
    )


def flatten_components(node: ComponentNode) -> Dict[int, int]:
    """Aggregate tree to type_id -> total quantity (leaves only)."""
    out: Dict[int, int] = {}

    def walk(n: ComponentNode) -> None:
        if not n.children:
            out[n.eve_type.id] = out.get(n.eve_type.id, 0) + n.quantity
        for c in n.children:
            walk(c)

    walk(node)
    return out


def get_flat_breakdown(
    eve_type: EveType, quantity: int = 1
) -> List[Tuple[EveType, int]]:
    """Flat list of (EveType, quantity) for all base components."""
    tree = break_down_type(eve_type, quantity=quantity)
    agg = flatten_components(tree)
    type_ids = list(agg.keys())
    types = {t.id: t for t in EveType.objects.filter(id__in=type_ids)}
    return [(types[tid], agg[tid]) for tid in type_ids if tid in types]


def tree_to_nested(node: ComponentNode) -> Dict[str, Any]:
    """Convert tree to a nested dict: name, type_id, quantity, source, depth, children."""
    return {
        "name": node.eve_type.name,
        "type_id": node.eve_type.id,
        "quantity": node.quantity,
        "source": node.source,
        "depth": node.depth,
        "children": [tree_to_nested(child) for child in node.children],
    }


def get_nested_breakdown(
    eve_type: EveType, quantity: int = 1
) -> Dict[str, Any]:
    """Full breakdown as a single nested dict (JSON-serializable, for tree UIs)."""
    return tree_to_nested(break_down_type(eve_type, quantity=quantity))
