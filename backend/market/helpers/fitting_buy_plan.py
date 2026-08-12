"""Build BOMs and shopping rows for fitting buy orders."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from eveuniverse.models import EveType

from industry.helpers.plan_stock import parse_stock_paste
from market.helpers.contract_match import fitting_type_quantities_bulk
from market.helpers.fitting_buy_allocations import prune_invalid_allocations
from market.models.fitting_buy_order import (
    FittingBuyOrder,
    FittingBuyOrderItem,
    FittingBuyOrderLine,
)


@dataclass(frozen=True)
class LineBom:
    line_id: int
    fitting_id: int
    quantity: int
    per_ship: dict[int, int]
    total: dict[int, int]


@dataclass(frozen=True)
class ShoppingPlan:
    needed: dict[int, int]
    stock: dict[int, int]
    buy: dict[int, int]
    unresolved_stock_names: list[str]
    line_boms: list[LineBom]
    type_names: dict[int, str]


def _apply_swaps(
    type_qty: dict[int, int], swaps: list | None
) -> dict[int, int]:
    if not swaps:
        return dict(type_qty)
    result = dict(type_qty)
    for swap in swaps:
        preferred = int(swap.get("preferred_type_id") or 0)
        substitute = int(swap.get("substitute_type_id") or 0)
        if not preferred or not substitute or preferred == substitute:
            continue
        qty = result.pop(preferred, 0)
        if qty:
            result[substitute] = result.get(substitute, 0) + qty
    return result


def line_type_quantities(
    lines: Iterable[FittingBuyOrderLine],
    *,
    include_hull: bool,
    apply_line_swaps: bool = True,
) -> list[LineBom]:
    lines = list(lines)
    if not lines:
        return []
    fittings = [line.fitting for line in lines]
    bulk = fitting_type_quantities_bulk(fittings)
    hull_ids = {f.id: f.ship_id for f in fittings}
    result: list[LineBom] = []
    for line in lines:
        per_ship = dict(bulk.get(line.fitting_id, {}))
        if not include_hull:
            ship_id = hull_ids.get(line.fitting_id)
            if ship_id:
                per_ship.pop(ship_id, None)

        quantity = int(line.quantity)
        swaps = line.swaps if apply_line_swaps else None
        swap_hull_qty = None
        if apply_line_swaps and swaps:
            raw_swap_qty = getattr(line, "swap_hull_qty", None)
            if raw_swap_qty is not None:
                swap_hull_qty = max(0, min(quantity, int(raw_swap_qty)))

        if (
            swaps
            and swap_hull_qty is not None
            and 0 < swap_hull_qty < quantity
        ):
            original_qty = quantity - swap_hull_qty
            swapped_per = _apply_swaps(per_ship, swaps)
            total: dict[int, int] = {}
            for tid, qty in per_ship.items():
                total[tid] = total.get(tid, 0) + qty * original_qty
            for tid, qty in swapped_per.items():
                total[tid] = total.get(tid, 0) + qty * swap_hull_qty
            result.append(
                LineBom(
                    line_id=line.id,
                    fitting_id=line.fitting_id,
                    quantity=quantity,
                    per_ship=swapped_per,
                    total=total,
                )
            )
            continue

        if apply_line_swaps:
            per_ship = _apply_swaps(per_ship, swaps)
        total = {tid: qty * quantity for tid, qty in per_ship.items()}
        result.append(
            LineBom(
                line_id=line.id,
                fitting_id=line.fitting_id,
                quantity=quantity,
                per_ship=per_ship,
                total=total,
            )
        )
    return result


def build_shopping_plan(order: FittingBuyOrder) -> ShoppingPlan:
    lines = list(
        order.lines.select_related("fitting").order_by("sort_order", "id")
    )
    line_boms = line_type_quantities(lines, include_hull=order.include_hull)
    needed: dict[int, int] = defaultdict(int)
    for bom in line_boms:
        for tid, qty in bom.total.items():
            needed[tid] += qty

    stock_result = parse_stock_paste(order.stock_paste)
    stock_remaining = dict(stock_result.by_type_id)
    stock_used: dict[int, int] = {}
    buy: dict[int, int] = {}
    for tid, need in sorted(needed.items()):
        owned = stock_remaining.get(tid, 0)
        used = min(owned, need)
        if used:
            stock_used[tid] = used
            stock_remaining[tid] = owned - used
            if stock_remaining[tid] <= 0:
                stock_remaining.pop(tid, None)
        buy[tid] = need - used

    all_ids = set(needed) | set(stock_used)
    type_names = dict(
        EveType.objects.filter(id__in=all_ids).values_list("id", "name")
    )

    return ShoppingPlan(
        needed=dict(needed),
        stock=stock_used,
        buy=buy,
        unresolved_stock_names=list(stock_result.unresolved_names),
        line_boms=line_boms,
        type_names=type_names,
    )


def sync_order_items(order: FittingBuyOrder) -> ShoppingPlan:
    plan = build_shopping_plan(order)
    existing = {row.eve_type_id: row for row in order.items.all()}
    keep_ids = set(plan.needed.keys())
    deleted = order.items.exclude(eve_type_id__in=keep_ids).delete()[0]

    to_create: list[FittingBuyOrderItem] = []
    to_update: list[FittingBuyOrderItem] = []
    bom_changed = deleted > 0
    for type_id, needed in plan.needed.items():
        stock_qty = plan.stock.get(type_id, 0)
        buy_qty = plan.buy.get(type_id, 0)
        row = existing.get(type_id)
        if row is None:
            to_create.append(
                FittingBuyOrderItem(
                    order=order,
                    eve_type_id=type_id,
                    needed_qty=needed,
                    stock_qty=stock_qty,
                    buy_qty=buy_qty,
                )
            )
            bom_changed = True
        elif (
            row.needed_qty != needed
            or row.stock_qty != stock_qty
            or row.buy_qty != buy_qty
        ):
            row.needed_qty = needed
            row.stock_qty = stock_qty
            row.buy_qty = buy_qty
            row.jita_sell_volume = None
            row.jita_order_count = None
            row.jita_sell_min = None
            to_update.append(row)
            bom_changed = True

    if to_create:
        FittingBuyOrderItem.objects.bulk_create(to_create)
    if to_update:
        FittingBuyOrderItem.objects.bulk_update(
            to_update,
            [
                "needed_qty",
                "stock_qty",
                "buy_qty",
                "jita_sell_volume",
                "jita_order_count",
                "jita_sell_min",
            ],
        )
    if bom_changed and order.jita_checked_at is not None:
        order.jita_checked_at = None
        order.save(update_fields=["jita_checked_at", "updated_at"])
    prune_invalid_allocations(order, plan)
    return plan


def compute_max_completable(
    line_boms: list[LineBom],
    buy_remaining_capacity: dict[int, int],
) -> dict[int, int]:
    result: dict[int, int] = {}
    for bom in line_boms:
        if bom.quantity <= 0:
            result[bom.line_id] = 0
            continue
        if not bom.per_ship:
            result[bom.line_id] = bom.quantity
            continue
        limits = []
        for tid, per in bom.per_ship.items():
            if per <= 0:
                continue
            available = buy_remaining_capacity.get(tid)
            if available is None:
                continue
            limits.append(available // per)
        if not limits:
            result[bom.line_id] = bom.quantity
        else:
            result[bom.line_id] = max(0, min(bom.quantity, *limits))
    return result


def multibuy_tsv(buy: dict[int, int], type_names: dict[int, str]) -> str:
    lines = []
    for tid, qty in sorted(
        buy.items(), key=lambda pair: type_names.get(pair[0], str(pair[0]))
    ):
        if qty <= 0:
            continue
        name = type_names.get(tid)
        if not name:
            continue
        lines.append(f"{name} {qty}")
    return "\n".join(lines)
