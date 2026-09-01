"""API serializers for fitting buy orders."""

from __future__ import annotations

import logging

from ninja import Schema

from eveuniverse.models import EveType

from fittings.models import EveFittingModuleSubstitution
from eveonline.helpers.characters import user_primary_character
from market.helpers.fitting_buy_allocations import (
    ALTERNATE_LIMIT,
    cached_jita_depth,
    cached_jita_sell_mins,
    effective_buy_map,
)
from market.helpers.fitting_buy_alternates import (
    cpu_pg_by_type,
    listed_substitutes_by_preferred,
    shopping_alternate_types_for,
)
from market.helpers.fitting_buy_contract_prices import build_contract_prices
from market.helpers.fitting_buy_eft import effective_efts_for_lines
from market.helpers.fitting_buy_fit_copies import build_fit_copies_by_line
from market.helpers.fitting_buy_guide import (
    multibuy_blocked,
    resolve_guide_step,
    shopping_landed_complete,
)
from market.helpers.fitting_buy_plan import (
    build_shopping_plan,
    compute_max_completable,
    multibuy_tsv,
)
from market.models.fitting_buy_order import (
    FittingBuyGuideStep,
    FittingBuyJitaCheck,
    FittingBuyJitaCheckStatus,
    FittingBuyOrder,
)

logger = logging.getLogger(__name__)


class FittingBuyAlternateSchema(Schema):
    type_id: int
    type_name: str
    jita_sell_volume: int | None = None
    jita_order_count: int | None = None
    jita_sell_min: str | None = None
    cpu: float | None = None
    pg: float | None = None


class FittingBuyAllocationSchema(Schema):
    type_id: int
    type_name: str
    qty: int


class FittingBuySwapSchema(Schema):
    preferred_type_id: int
    substitute_type_id: int
    notes: str = ""


class FittingBuyFitCopySchema(Schema):
    quantity: int
    eft: str
    is_swapped: bool = False
    variant_type_id: int | None = None
    variant_name: str = ""


class FittingBuyLineSchema(Schema):
    id: int
    fitting_id: int
    fitting_name: str
    ship_id: int
    quantity: int
    swaps: list[FittingBuySwapSchema]
    max_completable: int | None = None
    sort_order: int = 0
    eft: str = ""
    original_eft: str = ""
    original_quantity: int = 0
    swapped_quantity: int = 0
    has_swaps: bool = False
    fit_copies: list[FittingBuyFitCopySchema] = []


class FittingBuyItemSchema(Schema):
    type_id: int
    type_name: str
    needed_qty: int
    stock_qty: int
    buy_qty: int
    jita_sell_volume: int | None = None
    jita_order_count: int | None = None
    jita_sell_min: str | None = None
    unit_price: str | None = None
    shortfall: int | None = None
    is_short: bool = False
    cpu: float | None = None
    pg: float | None = None
    can_allocate: bool = False
    allocate_buy_qty: int | None = None
    allocated_from_type_id: int | None = None
    alternates: list[FittingBuyAlternateSchema] = []
    allocations: list[FittingBuyAllocationSchema] = []


class FittingBuySubstitutionSchema(Schema):
    fitting_id: int
    preferred_type_id: int
    preferred_name: str
    substitute_type_id: int
    substitute_name: str
    notes: str = ""


class FittingBuyOrderListShipSchema(Schema):
    fitting_id: int
    fitting_name: str
    ship_id: int
    quantity: int


class FittingBuyOrderListItemSchema(Schema):
    id: int
    status: str
    owner_id: int
    owner_username: str
    owner_character_id: int = 0
    owner_character_name: str = ""
    line_count: int
    ships: list[FittingBuyOrderListShipSchema]
    include_hull: bool
    jita_checked_at: str | None = None
    created_at: str
    updated_at: str
    is_owner: bool = False


class FittingBuyJitaCheckSchema(Schema):
    id: int
    status: str
    done_count: int
    total_count: int
    force_refresh: bool
    error: str = ""
    finished_at: str | None = None


class FittingBuyIndustrySourceSchema(Schema):
    type_id: int
    type_name: str
    unit_price: str
    order_id: int
    public_short_code: str = ""


class FittingBuyContractPriceSchema(Schema):
    line_id: int
    fitting_id: int
    fitting_name: str
    ship_id: int
    ship_name: str = ""
    eft: str = ""
    quantity: int
    is_swapped: bool = False
    variant_name: str = ""
    hull_cost: str | None = None
    hull_cost_from_jita: bool = False
    hull_cost_source: str = ""
    hull_cost_industry_order_id: int | None = None
    hull_cost_industry_short_code: str = ""
    fitting_cost: str | None = None
    landed_per_ship: str | None = None
    landed_complete: bool = False
    missing_type_names: list[str] = []
    landed_plus_20: str | None = None
    jita_sell_per_ship: str | None = None
    jita_plus_20: str | None = None
    industry_sources: list[FittingBuyIndustrySourceSchema] = []


class FittingBuyOrderDetailSchema(Schema):
    id: int
    status: str
    guide_step: str = "stock"
    notes: str
    owner_id: int
    owner_username: str
    owner_character_id: int = 0
    owner_character_name: str = ""
    stock_paste: str
    include_hull: bool
    jita_checked_at: str | None = None
    created_at: str
    updated_at: str
    is_owner: bool
    lines: list[FittingBuyLineSchema]
    items: list[FittingBuyItemSchema]
    multibuy: str
    fits_eft: str = ""
    unresolved_stock_names: list[str]
    substitutions: list[FittingBuySubstitutionSchema]
    active_jita_check: FittingBuyJitaCheckSchema | None = None
    contract_prices: list[FittingBuyContractPriceSchema] = []
    multibuy_blocked: bool = False
    multibuy_block_reason: str = ""
    shopping_landed_complete: bool = False


def _iso(dt) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def _owner_fields(order: FittingBuyOrder) -> dict:
    username = getattr(order.owner, "username", str(order.owner_id))
    primary = user_primary_character(order.owner) if order.owner_id else None
    character_id = int(primary.character_id) if primary else 0
    character_name = (primary.character_name if primary else "") or username
    return {
        "owner_id": order.owner_id,
        "owner_username": username,
        "owner_character_id": character_id,
        "owner_character_name": character_name,
    }


def _is_owner(order: FittingBuyOrder, request_user) -> bool:
    return bool(
        request_user
        and request_user.is_authenticated
        and (request_user.id == order.owner_id or request_user.is_staff)
    )


def serialize_jita_check(check: FittingBuyJitaCheck) -> dict:
    return {
        "id": check.id,
        "status": check.status,
        "done_count": check.done_count,
        "total_count": check.total_count,
        "force_refresh": check.force_refresh,
        "error": check.error or "",
        "finished_at": _iso(check.finished_at),
    }


def serialize_order_list_item(order, request_user=None) -> dict:
    lines = list(
        order.lines.select_related("fitting").order_by("sort_order", "id")
    )
    ships = [
        {
            "fitting_id": line.fitting_id,
            "fitting_name": line.fitting.name,
            "ship_id": line.fitting.ship_id,
            "quantity": line.quantity,
        }
        for line in lines
    ]
    return {
        "id": order.id,
        "status": order.status,
        **_owner_fields(order),
        "line_count": getattr(order, "line_count", len(ships)),
        "ships": ships,
        "include_hull": order.include_hull,
        "jita_checked_at": _iso(order.jita_checked_at),
        "created_at": _iso(order.created_at),
        "updated_at": _iso(order.updated_at),
        "is_owner": _is_owner(order, request_user),
    }


def _display_shortfall(
    buy_qty: int, jita_sell_volume: int | None
) -> int | None:
    if jita_sell_volume is None:
        return None
    return max(0, int(buy_qty) - int(jita_sell_volume))


def serialize_order_detail(  # noqa: C901
    order: FittingBuyOrder, request_user=None
) -> dict:
    plan = build_shopping_plan(order)
    items = list(order.items.select_related("eve_type"))
    items_by_id = {row.eve_type_id: row for row in items}
    effective_buy = effective_buy_map(order, plan)
    allocations_raw = order.shopping_allocations or {}

    capacity: dict[int, int] = {}
    for row in items:
        if row.buy_qty > 0 and row.jita_sell_volume is not None:
            capacity[row.eve_type_id] = int(row.jita_sell_volume)

    checked = order.jita_checked_at is not None
    max_completable = (
        compute_max_completable(plan.line_boms, capacity) if checked else {}
    )

    allocation_type_ids: set[int] = set()
    preferred_ids_with_alloc: set[int] = set()
    for preferred_key, raw_entries in allocations_raw.items():
        try:
            preferred_ids_with_alloc.add(int(preferred_key))
        except (TypeError, ValueError):
            continue
        for entry in raw_entries or []:
            try:
                allocation_type_ids.add(int(entry.get("type_id") or 0))
            except (TypeError, ValueError):
                continue
    allocation_type_ids.discard(0)

    # Alternates for BOM rows that are short on Jita, or already have a split.
    allocate_preferred_types: list = []
    for row in items:
        bom_short = bool(row.shortfall and row.shortfall > 0)
        if bom_short or row.eve_type_id in preferred_ids_with_alloc:
            allocate_preferred_types.append(row.eve_type)

    listed_by_preferred = listed_substitutes_by_preferred(
        line.fitting_id for line in order.lines.all()
    )
    prices = cached_jita_sell_mins(order, items_by_id=items_by_id)
    alternates_by_type: dict[int, list[dict]] = {}
    for eve_type in allocate_preferred_types:
        rows = []
        for alt in shopping_alternate_types_for(
            eve_type,
            limit=ALTERNATE_LIMIT,
            listed_substitute_ids=listed_by_preferred.get(eve_type.id, set()),
            jita_sell_min_by_type=prices,
        ):
            depth = cached_jita_depth(order, alt.id, items_by_id=items_by_id)
            allocation_type_ids.add(alt.id)
            rows.append(
                {
                    "type_id": alt.id,
                    "type_name": alt.name,
                    **depth,
                }
            )
        alternates_by_type[eve_type.id] = rows

    type_names = dict(plan.type_names)
    missing_name_ids = (
        set(effective_buy)
        | allocation_type_ids
        | {row.eve_type_id for row in items}
    ) - set(type_names)
    if missing_name_ids:
        type_names.update(
            EveType.objects.filter(id__in=missing_name_ids).values_list(
                "id", "name"
            )
        )

    cpu_pg = cpu_pg_by_type(
        set(effective_buy)
        | {row.eve_type_id for row in items}
        | allocation_type_ids
    )

    # Preferred → which allocation-only types came from it (for UI provenance).
    allocated_from: dict[int, int] = {}
    for preferred_key, raw_entries in allocations_raw.items():
        try:
            preferred_id = int(preferred_key)
        except (TypeError, ValueError):
            continue
        for entry in raw_entries or []:
            try:
                tid = int(entry.get("type_id") or 0)
                qty = int(entry.get("qty") or 0)
            except (TypeError, ValueError):
                continue
            if tid and qty > 0 and tid != preferred_id:
                allocated_from[tid] = preferred_id

    def allocations_for(preferred_id: int) -> list[dict]:
        raw_entries = allocations_raw.get(str(preferred_id)) or []
        return [
            {
                "type_id": int(entry.get("type_id") or 0),
                "type_name": type_names.get(
                    int(entry.get("type_id") or 0),
                    str(entry.get("type_id") or ""),
                ),
                "qty": int(entry.get("qty") or 0),
            }
            for entry in raw_entries
            if int(entry.get("type_id") or 0)
            and int(entry.get("qty") or 0) > 0
        ]

    def display_row(
        *,
        type_id: int,
        buy_qty: int,
        needed_qty: int,
        stock_qty: int,
        jita_sell_volume: int | None,
        jita_order_count: int | None,
        jita_sell_min: str | None,
        unit_price: str | None,
        allocated_from_type_id: int | None = None,
        can_allocate: bool = False,
        allocate_buy_qty: int | None = None,
        alternates: list[dict] | None = None,
        allocations: list[dict] | None = None,
    ) -> dict:
        shortfall = _display_shortfall(buy_qty, jita_sell_volume)
        cpu, pg = cpu_pg.get(type_id, (None, None))
        return {
            "type_id": type_id,
            "type_name": type_names.get(type_id, str(type_id)),
            "needed_qty": needed_qty,
            "stock_qty": stock_qty,
            "buy_qty": buy_qty,
            "jita_sell_volume": jita_sell_volume,
            "jita_order_count": jita_order_count,
            "jita_sell_min": jita_sell_min,
            "unit_price": unit_price,
            "shortfall": shortfall,
            "is_short": bool(shortfall and shortfall > 0),
            "cpu": cpu,
            "pg": pg,
            "can_allocate": can_allocate,
            "allocate_buy_qty": allocate_buy_qty,
            "allocated_from_type_id": allocated_from_type_id,
            "alternates": alternates or [],
            "allocations": allocations or [],
        }

    item_schemas: list[dict] = []
    seen: set[int] = set()

    # Effective buys first (what Multibuy / purchase list should show).
    for type_id, buy_qty in sorted(
        effective_buy.items(),
        key=lambda pair: type_names.get(pair[0], str(pair[0])),
    ):
        if buy_qty <= 0:
            continue
        seen.add(type_id)
        row = items_by_id.get(type_id)
        alts = []
        allocs = []
        can_allocate = False
        if row is not None:
            alts_raw = alternates_by_type.get(type_id, [])
            fitted = []
            for alt in alts_raw:
                alt_cpu, alt_pg = cpu_pg.get(alt["type_id"], (None, None))
                fitted.append({**alt, "cpu": alt_cpu, "pg": alt_pg})
            alts = fitted
            allocs = allocations_for(type_id)
            can_allocate = bool(alts) and (
                bool(row.shortfall and row.shortfall > 0)
                or type_id in preferred_ids_with_alloc
            )
            from_id = allocated_from.get(type_id)
            item_schemas.append(
                display_row(
                    type_id=type_id,
                    buy_qty=buy_qty,
                    needed_qty=buy_qty if from_id else row.needed_qty,
                    stock_qty=row.stock_qty,
                    jita_sell_volume=row.jita_sell_volume,
                    jita_order_count=row.jita_order_count,
                    jita_sell_min=(
                        str(row.jita_sell_min)
                        if row.jita_sell_min is not None
                        else None
                    ),
                    unit_price=(
                        str(row.unit_price)
                        if row.unit_price is not None
                        else None
                    ),
                    allocated_from_type_id=from_id,
                    can_allocate=can_allocate,
                    allocate_buy_qty=row.buy_qty if can_allocate else None,
                    alternates=alts,
                    allocations=allocs,
                )
            )
        else:
            depth = cached_jita_depth(order, type_id, items_by_id=items_by_id)
            item_schemas.append(
                display_row(
                    type_id=type_id,
                    buy_qty=buy_qty,
                    needed_qty=buy_qty,
                    stock_qty=0,
                    jita_sell_volume=depth.get("jita_sell_volume"),
                    jita_order_count=depth.get("jita_order_count"),
                    jita_sell_min=depth.get("jita_sell_min"),
                    unit_price=None,
                    allocated_from_type_id=allocated_from.get(type_id),
                )
            )

    # Stocked BOM rows (buy 0) and preferred rows fully replaced but editable.
    for row in items:
        if row.eve_type_id in seen:
            continue
        alts_raw = alternates_by_type.get(row.eve_type_id, [])
        fitted = []
        for alt in alts_raw:
            alt_cpu, alt_pg = cpu_pg.get(alt["type_id"], (None, None))
            fitted.append({**alt, "cpu": alt_cpu, "pg": alt_pg})
        allocs = allocations_for(row.eve_type_id)
        can_allocate = bool(fitted) and (
            bool(row.shortfall and row.shortfall > 0)
            or row.eve_type_id in preferred_ids_with_alloc
        )
        # Skip empty preferred with nothing to edit and nothing on hand.
        if (
            row.buy_qty <= 0
            and row.stock_qty <= 0
            and not can_allocate
            and not allocs
        ):
            continue
        display_buy = effective_buy.get(row.eve_type_id, 0)
        from_id = allocated_from.get(row.eve_type_id)
        item_schemas.append(
            display_row(
                type_id=row.eve_type_id,
                buy_qty=display_buy,
                needed_qty=display_buy if from_id else row.needed_qty,
                stock_qty=row.stock_qty,
                jita_sell_volume=row.jita_sell_volume,
                jita_order_count=row.jita_order_count,
                jita_sell_min=(
                    str(row.jita_sell_min)
                    if row.jita_sell_min is not None
                    else None
                ),
                unit_price=(
                    str(row.unit_price) if row.unit_price is not None else None
                ),
                allocated_from_type_id=from_id,
                can_allocate=can_allocate,
                allocate_buy_qty=row.buy_qty if can_allocate else None,
                alternates=fitted,
                allocations=allocs,
            )
        )

    item_schemas.sort(
        key=lambda item: (not item["is_short"], item["type_name"])
    )

    order_lines = list(
        order.lines.select_related("fitting").order_by("sort_order", "id")
    )
    eft_by_line = effective_efts_for_lines(order_lines)
    fit_copies_by_line = build_fit_copies_by_line(order, order_lines)
    lines = []
    for line in order_lines:
        swaps = []
        for swap in line.swaps or []:
            preferred = int(swap.get("preferred_type_id") or 0)
            substitute = int(swap.get("substitute_type_id") or 0)
            if not preferred or not substitute:
                continue
            swaps.append(
                {
                    "preferred_type_id": preferred,
                    "substitute_type_id": substitute,
                    "notes": str(swap.get("notes") or ""),
                }
            )
        original_eft = line.fitting.eft_format or ""
        swapped_eft = eft_by_line.get(line.id, "")
        quantity = int(line.quantity)
        fit_copies = fit_copies_by_line.get(line.id) or [
            {
                "quantity": quantity,
                "eft": swapped_eft if swaps else original_eft,
                "is_swapped": bool(swaps),
                "variant_type_id": None,
                "variant_name": "",
            }
        ]
        original_quantity = sum(
            copy["quantity"] for copy in fit_copies if not copy["is_swapped"]
        )
        swapped_quantity = sum(
            copy["quantity"] for copy in fit_copies if copy["is_swapped"]
        )
        lines.append(
            {
                "id": line.id,
                "fitting_id": line.fitting_id,
                "fitting_name": line.fitting.name,
                "ship_id": line.fitting.ship_id,
                "quantity": quantity,
                "swaps": swaps,
                "max_completable": (
                    max_completable.get(line.id) if checked else None
                ),
                "sort_order": line.sort_order,
                "eft": swapped_eft if swaps else original_eft,
                "original_eft": original_eft,
                "original_quantity": original_quantity,
                "swapped_quantity": swapped_quantity,
                "has_swaps": bool(swaps) or swapped_quantity > 0,
                "fit_copies": fit_copies,
            }
        )
    fitting_ids = [line.fitting_id for line in order_lines]
    short_preferred_ids = {
        item["type_id"]
        for item in item_schemas
        if item["is_short"] or item["can_allocate"]
    }
    subs = []
    for row in EveFittingModuleSubstitution.objects.filter(
        fitting_id__in=fitting_ids
    ).select_related("preferred_module", "substitute_module"):
        if (
            short_preferred_ids
            and row.preferred_module_id not in short_preferred_ids
        ):
            continue
        subs.append(
            {
                "fitting_id": row.fitting_id,
                "preferred_type_id": row.preferred_module_id,
                "preferred_name": row.preferred_module.name,
                "substitute_type_id": row.substitute_module_id,
                "substitute_name": row.substitute_module.name,
                "notes": row.notes or "",
            }
        )

    active = (
        order.jita_checks.filter(
            status__in=[
                FittingBuyJitaCheckStatus.PENDING,
                FittingBuyJitaCheckStatus.RUNNING,
            ]
        )
        .order_by("-created_at")
        .first()
    )

    blocked, block_reason = multibuy_blocked(order, plan)
    landed_done = shopping_landed_complete(order, plan)
    guide_step = resolve_guide_step(order, plan)
    contract_prices: list[dict] = []
    if guide_step == FittingBuyGuideStep.CONTRACT:
        try:
            contract_prices = build_contract_prices(order)
        except Exception:
            logger.exception(
                "Failed to build contract prices for fitting buy order %s",
                order.pk,
            )

    return {
        "id": order.id,
        "status": order.status,
        "guide_step": guide_step,
        "notes": order.notes,
        **_owner_fields(order),
        "stock_paste": order.stock_paste or "",
        "include_hull": order.include_hull,
        "jita_checked_at": _iso(order.jita_checked_at),
        "created_at": _iso(order.created_at),
        "updated_at": _iso(order.updated_at),
        "is_owner": _is_owner(order, request_user),
        "lines": lines,
        "items": item_schemas,
        "multibuy": multibuy_tsv(effective_buy, type_names),
        "fits_eft": "\n\n".join(
            block
            for line_data in lines
            for copy in line_data["fit_copies"]
            if (block := (copy.get("eft") or "").strip())
        ),
        "unresolved_stock_names": plan.unresolved_stock_names,
        "substitutions": subs,
        "active_jita_check": serialize_jita_check(active) if active else None,
        "contract_prices": contract_prices,
        "multibuy_blocked": blocked,
        "multibuy_block_reason": block_reason,
        "shopping_landed_complete": landed_done,
    }
