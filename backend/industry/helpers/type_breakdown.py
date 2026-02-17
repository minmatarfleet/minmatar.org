"""
Break down an EveType into its components using the eveuniverse data model.

Components come from: EveTypeMaterial (e.g. reprocessing), blueprint
manufacturing (activity_id=1), or reactions (activity_id=11). Components
that are themselves built from blueprints/reactions are expanded recursively.

Blueprint/reaction data is loaded from the SDE on demand when breaking down
a product type (e.g. a ship).

IndustryProduct.breakdown stores the full tree (all the way to leaves) so
callers can traverse to any depth; use get_breakdown_for_industry_product()
to fetch or compute (and store) that full tree, and optionally truncate to
a max_depth when returning.
"""

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from eveuniverse.models import (
    EveIndustryActivityMaterial,
    EveIndustryActivityProduct,
    EveType,
    EveTypeMaterial,
)

from industry.models import IndustryProduct, IndustryProductStrategy

ACTIVITY_MANUFACTURING = 1
ACTIVITY_REACTION = 11

# Cap recursion depth to avoid stack overflow and long-running requests (e.g. gunicorn worker exit).
MAX_BREAKDOWN_DEPTH_DEFAULT = 30


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
            EveIndustryActivityProduct.objects._fetch_sde_data_cached()  # pylint: disable=protected-access
        )
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
    """Aggregate tree to type_id -> total quantity (leaves only). Iterative to avoid recursion overflow."""
    out: Dict[int, int] = {}
    stack: List[ComponentNode] = [node]
    while stack:
        n = stack.pop()
        if not n.children:
            out[n.eve_type.id] = out.get(n.eve_type.id, 0) + n.quantity
        for c in n.children:
            stack.append(c)
    return out


def get_flat_breakdown(
    eve_type: EveType,
    quantity: int = 1,
    max_depth: Optional[int] = None,
) -> List[Tuple[EveType, int]]:
    """Flat list of (EveType, quantity) for all base components."""
    if max_depth is None:
        max_depth = MAX_BREAKDOWN_DEPTH_DEFAULT
    tree = break_down_type(eve_type, quantity=quantity, max_depth=max_depth)
    agg = flatten_components(tree)
    type_ids = list(agg.keys())
    types = {t.id: t for t in EveType.objects.filter(id__in=type_ids)}
    return [(types[tid], agg[tid]) for tid in type_ids if tid in types]


def tree_to_nested(node: ComponentNode) -> Dict[str, Any]:
    """Convert tree to a nested dict (iterative to avoid recursion overflow)."""
    if not node.children:
        return {
            "name": node.eve_type.name,
            "type_id": node.eve_type.id,
            "quantity": node.quantity,
            "source": node.source,
            "depth": node.depth,
            "children": [],
        }
    stack: List[Tuple[ComponentNode, Optional[List[Any]]]] = [(node, None)]
    result: Optional[Dict[str, Any]] = None
    while stack:
        n, parent_children = stack.pop()
        d: Dict[str, Any] = {
            "name": n.eve_type.name,
            "type_id": n.eve_type.id,
            "quantity": n.quantity,
            "source": n.source,
            "depth": n.depth,
            "children": [],
        }
        for child in reversed(n.children):
            stack.append((child, d["children"]))
        if parent_children is not None:
            parent_children.append(d)
        else:
            result = d
    return result or {}


def get_nested_breakdown(
    eve_type: EveType,
    quantity: int = 1,
    max_depth: Optional[int] = None,
) -> Dict[str, Any]:
    """Full breakdown as a single nested dict (JSON-serializable, for tree UIs)."""
    if max_depth is None:
        max_depth = MAX_BREAKDOWN_DEPTH_DEFAULT
    tree = break_down_type(eve_type, quantity=quantity, max_depth=max_depth)
    return tree_to_nested(tree)


def _scale_nested_quantity(node: Dict[str, Any], factor: int) -> None:
    """Multiply quantity in node and all descendants by factor (in place)."""
    node["quantity"] = node.get("quantity", 1) * factor
    for child in node.get("children", []):
        _scale_nested_quantity(child, factor)


def scale_nested_breakdown(
    data: Dict[str, Any],
    quantity: int,
) -> Dict[str, Any]:
    """Return a deep copy of the nested breakdown with all quantities scaled by quantity."""
    result = copy.deepcopy(data)
    _scale_nested_quantity(result, quantity)
    return result


def truncate_breakdown_to_depth(
    data: Dict[str, Any],
    max_depth: int,
) -> Dict[str, Any]:
    """
    Return a deep copy of the nested breakdown with nodes below max_depth removed.
    Nodes at depth == max_depth get children=[] so you can traverse to any depth.
    """
    result = copy.deepcopy(data)
    depth = result.get("depth", 0)
    if depth >= max_depth:
        result["children"] = []
        return result
    result["children"] = [
        truncate_breakdown_to_depth(c, max_depth)
        for c in result.get("children", [])
    ]
    return result


def get_full_nested_breakdown(eve_type: EveType) -> Dict[str, Any]:
    """
    Compute the full breakdown tree (no depth limit) as a nested dict.
    Used when storing on IndustryProduct so the stored tree goes all the way down.
    """
    tree = break_down_type(
        eve_type,
        quantity=1,
        max_depth=None,
    )
    return tree_to_nested(tree)


def get_breakdown_for_industry_product(
    eve_type: EveType,
    quantity: int = 1,
    max_depth: Optional[int] = None,
    store: bool = True,
) -> Dict[str, Any]:
    """
    Get nested breakdown for this type from IndustryProduct if stored, else compute
    (and optionally store) the full tree. Every IndustryProduct stores the full
    traverse all the way down; you can pass max_depth to truncate the returned
    tree to a given depth.

    If store=True and the product has no breakdown, it will be computed with
    full depth and saved. When returning, quantities are scaled by quantity and
    the tree is truncated to max_depth if set.
    """
    product = IndustryProduct.objects.filter(eve_type=eve_type).first()
    base: Optional[Dict[str, Any]] = None

    if product is not None and product.breakdown:
        base = product.breakdown
    else:
        base = get_full_nested_breakdown(eve_type)
        if store:
            if product is not None:
                product.breakdown = base
                product.save(update_fields=["breakdown"])
            else:
                IndustryProduct.objects.create(
                    eve_type=eve_type,
                    strategy=IndustryProductStrategy.INTEGRATED,
                    breakdown=base,
                )

    out = scale_nested_breakdown(base, quantity)
    if max_depth is not None:
        out = truncate_breakdown_to_depth(out, max_depth)
    return out


def flatten_nested_breakdown_to_quantities(
    data: Dict[str, Any],
) -> Dict[int, int]:
    """
    Aggregate a nested breakdown dict to type_id -> total quantity (leaves only).
    Use after get_breakdown_for_industry_product when you need a flat list of base materials.
    """
    out: Dict[int, int] = {}
    stack: List[Dict[str, Any]] = [data]
    while stack:
        node = stack.pop()
        children = node.get("children", [])
        if not children:
            tid = node.get("type_id")
            if tid is not None:
                out[tid] = out.get(tid, 0) + node.get("quantity", 0)
        for c in children:
            stack.append(c)
    return out


def _collect_type_ids_from_breakdown(
    node: Dict[str, Any], out: Set[int]
) -> None:
    """Collect all type_id values from a nested breakdown tree."""
    tid = node.get("type_id")
    if tid is not None:
        out.add(tid)
    for child in node.get("children", []):
        _collect_type_ids_from_breakdown(child, out)


def _enrich_node_with_industry_product_id(
    node: Dict[str, Any],
    type_id_to_product_id: Dict[int, int],
) -> None:
    """Add industry_product_id to node and all descendants (in place)."""
    tid = node.get("type_id")
    node["industry_product_id"] = (
        type_id_to_product_id.get(tid) if tid else None
    )
    for child in node.get("children", []):
        _enrich_node_with_industry_product_id(child, type_id_to_product_id)


def enrich_breakdown_with_industry_product_ids(
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Add industry_product_id to each node in the nested breakdown (in place).
    Nodes whose type has an IndustryProduct get its id; others get None.
    Enables fetching a node's breakdown by GET /products/{industry_product_id}/breakdown.
    """
    type_ids: Set[int] = set()
    _collect_type_ids_from_breakdown(data, type_ids)
    if not type_ids:
        return data
    product_map = dict(
        IndustryProduct.objects.filter(eve_type_id__in=type_ids).values_list(
            "eve_type_id", "id"
        )
    )
    _enrich_node_with_industry_product_id(data, product_map)
    return data
