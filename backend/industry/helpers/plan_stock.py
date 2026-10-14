"""Apply pasted EVE inventory stock against planner material needs."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import (
    Callable,
    Dict,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Tuple,
)

from buyback.helpers.classify import resolve_types_by_name
from buyback.helpers.ore_names import buyback_ore_family
from buyback.helpers.paste import parse_eve_paste
from industry.helpers.compressed_ore import (
    ORE_BATCH_SIZE,
    reprocess_output,
)


@dataclass(frozen=True)
class StockParseResult:
    """Resolved on-hand quantities from an inventory / Multibuy paste."""

    by_type_id: Dict[int, int]
    by_name: Dict[str, int]
    name_to_type_id: Dict[str, int]
    unresolved_names: List[str]


@dataclass(frozen=True)
class StockAppliedRow:
    type_id: int
    name: str
    needed: int
    owned: int
    used: int
    remaining: int


def parse_stock_paste(paste: Optional[str]) -> StockParseResult:
    """Parse EVE paste into type_id/name quantity maps; unknown names listed."""
    empty = StockParseResult(
        by_type_id={},
        by_name={},
        name_to_type_id={},
        unresolved_names=[],
    )
    if not paste or not str(paste).strip():
        return empty

    lines = parse_eve_paste(paste)
    if not lines:
        return empty

    names = [line.name for line in lines]
    resolved = resolve_types_by_name(names)

    by_type_id: Dict[int, int] = {}
    by_name: Dict[str, int] = {}
    name_to_type_id: Dict[str, int] = {}
    unresolved: List[str] = []

    for line in lines:
        eve_type = resolved.get(line.name)
        if eve_type is None:
            unresolved.append(line.name)
            continue
        by_type_id[eve_type.id] = (
            by_type_id.get(eve_type.id, 0) + line.quantity
        )
        by_name[eve_type.name] = by_name.get(eve_type.name, 0) + line.quantity
        name_to_type_id[eve_type.name] = eve_type.id

    return StockParseResult(
        by_type_id=by_type_id,
        by_name=by_name,
        name_to_type_id=name_to_type_id,
        unresolved_names=list(dict.fromkeys(unresolved)),
    )


def _consume_stock_qty(
    stock_map: MutableMapping,
    key,
    used: int,
) -> None:
    """Decrement a stock map entry; drop keys that hit zero."""
    if used <= 0 or key not in stock_map:
        return
    left = int(stock_map[key]) - used
    if left > 0:
        stock_map[key] = left
    else:
        stock_map.pop(key, None)


def apply_stock_to_leaf_materials(
    leaf: Mapping[int, Tuple[str, int]],
    stock_by_type_id: MutableMapping[int, int],
    *,
    stock_by_name: Optional[MutableMapping[str, int]] = None,
) -> Tuple[Dict[int, Tuple[str, int]], List[StockAppliedRow]]:
    """
    Subtract owned stock from leaf BOM quantities.

    Types fully covered are omitted from the remaining map. Only types that
    appear in both leaf demand and stock are reported in ``applied``.
    Consumes matching quantities from ``stock_by_type_id`` (and optional
    ``stock_by_name``) so a later compressed-ore pass cannot double-count.
    """
    remaining: Dict[int, Tuple[str, int]] = {}
    applied: List[StockAppliedRow] = []

    for type_id, (name, needed) in leaf.items():
        owned = int(stock_by_type_id.get(type_id, 0) or 0)
        if owned <= 0:
            remaining[type_id] = (name, needed)
            continue
        used = min(needed, owned)
        left = needed - used
        applied.append(
            StockAppliedRow(
                type_id=type_id,
                name=name,
                needed=needed,
                owned=owned,
                used=used,
                remaining=left,
            )
        )
        _consume_stock_qty(stock_by_type_id, type_id, used)
        if stock_by_name is not None:
            _consume_stock_qty(stock_by_name, name, used)
        if left > 0:
            remaining[type_id] = (name, left)

    applied.sort(key=lambda row: row.name.lower())
    return remaining, applied


def apply_stock_to_named_bucket(
    bucket: MutableMapping[str, int],
    stock_by_name: MutableMapping[str, int],
    *,
    name_to_type_id: Optional[Mapping[str, int]] = None,
) -> List[StockAppliedRow]:
    """
    Subtract stock from a name→qty shopping bucket in place.

    Zero remaining entries are removed. Returns applied rows for matched names.
    Consumes matching quantities from ``stock_by_name``.
    """
    applied: List[StockAppliedRow] = []
    for name in list(bucket.keys()):
        needed = int(bucket.get(name, 0) or 0)
        if needed <= 0:
            bucket.pop(name, None)
            continue
        owned = int(stock_by_name.get(name, 0) or 0)
        if owned <= 0:
            continue
        used = min(needed, owned)
        left = needed - used
        type_id = 0
        if name_to_type_id is not None:
            type_id = int(name_to_type_id.get(name, 0) or 0)
        applied.append(
            StockAppliedRow(
                type_id=type_id,
                name=name,
                needed=needed,
                owned=owned,
                used=used,
                remaining=left,
            )
        )
        _consume_stock_qty(stock_by_name, name, used)
        if left > 0:
            bucket[name] = left
        else:
            bucket.pop(name, None)
    applied.sort(key=lambda row: row.name.lower())
    return applied


def _leaf_type_by_name(
    leaf: Mapping[int, Tuple[str, int]],
) -> Dict[str, int]:
    indexed: Dict[str, int] = {}
    for type_id, pair in leaf.items():
        indexed[pair[0]] = type_id
    return indexed


def _variant_batches_needed(
    leaf: Mapping[int, Tuple[str, int]],
    per_batch: Mapping[str, int],
) -> int:
    leaf_index = _leaf_type_by_name(leaf)
    batches_needed = 0
    for mineral, produced in per_batch.items():
        type_id = leaf_index.get(mineral)
        if type_id is None or produced <= 0:
            continue
        demand = int(leaf[type_id][1])
        if demand <= 0:
            continue
        batches_needed = max(batches_needed, math.ceil(demand / produced))
    return batches_needed


def _subtract_reprocess_outputs(
    leaf: MutableMapping[int, Tuple[str, int]],
    outputs: Mapping[str, int],
) -> bool:
    leaf_index = _leaf_type_by_name(leaf)
    credited = False
    for mineral, produced in outputs.items():
        type_id = leaf_index.get(mineral)
        if type_id is None or produced <= 0 or type_id not in leaf:
            continue
        mineral_name, needed = leaf[type_id]
        take = min(int(needed), int(produced))
        if take <= 0:
            continue
        left = int(needed) - take
        if left > 0:
            leaf[type_id] = (mineral_name, left)
        else:
            leaf.pop(type_id, None)
        credited = True
    return credited


def credit_reprocessed_ore_stock(
    leaf: MutableMapping[int, Tuple[str, int]],
    stock_by_type_id: MutableMapping[int, int],
    stock_by_name: MutableMapping[str, int],
    *,
    name_to_type_id: Optional[Mapping[str, int]] = None,
    refine_rate_for: Callable[[str], float],
) -> List[StockAppliedRow]:
    """
    Turn grade, moon, and uncompressed ore stock into minerals.

    Exact ``Compressed {base}`` stacks stay in stock so a later pass can
    match the shopping list 1:1. II/III/IV-Grade and Brimful/Glistening
    stacks are not on that list; their reprocess output covers leaf minerals
    before the compressed buy is sized. Only whole 100-unit portions count.
    """
    applied: List[StockAppliedRow] = []
    for name in list(stock_by_name.keys()):
        family = buyback_ore_family(name)
        if not family or name == f"Compressed {family}":
            continue
        owned = int(stock_by_name.get(name, 0) or 0)
        batches_available = owned // ORE_BATCH_SIZE
        if batches_available <= 0:
            continue
        rate = float(refine_rate_for(name))
        if rate <= 0:
            continue
        per_batch = reprocess_output(name, ORE_BATCH_SIZE, rate)
        if not per_batch:
            continue
        batches_needed = _variant_batches_needed(leaf, per_batch)
        batches = min(batches_available, batches_needed)
        if batches <= 0:
            continue
        used = batches * ORE_BATCH_SIZE
        if not _subtract_reprocess_outputs(
            leaf, reprocess_output(name, used, rate)
        ):
            continue
        _consume_stock_qty(stock_by_name, name, used)
        type_id = 0
        if name_to_type_id is not None:
            type_id = int(name_to_type_id.get(name, 0) or 0)
        if type_id:
            _consume_stock_qty(stock_by_type_id, type_id, used)
        applied.append(
            StockAppliedRow(
                type_id=type_id,
                name=name,
                needed=used,
                owned=owned,
                used=used,
                remaining=owned - used,
            )
        )
    applied.sort(key=lambda row: row.name.lower())
    return applied


def apply_stock_to_compressed_ore_plan(
    ore_plan,
    stock_by_name: MutableMapping[str, int],
    *,
    name_to_type_id: Optional[Mapping[str, int]] = None,
) -> List[StockAppliedRow]:
    """Reduce compressed-ore Multibuy buckets by remaining on-hand stock."""
    applied: List[StockAppliedRow] = []
    for bucket in (
        ore_plan.moon_ore_compressed,
        ore_plan.belt_ore_compressed,
        ore_plan.ice_compressed,
        ore_plan.mineral_imports,
        ore_plan.pi_other_imports,
        ore_plan.ice_imports,
        ore_plan.other_imports,
    ):
        applied.extend(
            apply_stock_to_named_bucket(
                bucket,
                stock_by_name,
                name_to_type_id=name_to_type_id,
            )
        )
    if not (
        ore_plan.moon_ore_compressed
        or ore_plan.belt_ore_compressed
        or ore_plan.ice_compressed
    ):
        ore_plan.reprocessing_tax = 0.0
    applied.sort(key=lambda row: row.name.lower())
    return applied
