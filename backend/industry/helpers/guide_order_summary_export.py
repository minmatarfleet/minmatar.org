"""
Build and serialize guide-hull order summary rows for the frontend data module.

Used by ``export_guide_order_summary`` so refreshes are not manual shell work.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from django.conf import settings
from eveuniverse.models import EveType

from industry.helpers.blueprint_efficiency import (
    default_blueprint_me_te_percent,
    is_faction_navy_hull,
)
from industry.helpers.build_planner import plan_build
from industry.helpers.compressed_ore import build_compressed_ore_plan
from industry.helpers.cost_breakdown import (
    build_plan_cost_breakdown,
    jita_sell_prices_by_type_id,
)
from industry.helpers.facility_profiles import get_facility_reprocessing_tax
from industry.helpers.loyalty_store import (
    get_offer_for_blueprint_type,
    navy_bpc_cost_for_plan,
    resolve_isk_per_lp,
)
from industry.helpers.reprocessing_skills import resolve_refine_rate
from industry.helpers.type_breakdown import get_blueprint_or_reaction_type_id

ORDER_QTY = 100
MIN_ORDER_PROFIT_ISK = 25_000_000
FACILITY_KEY = "amamake"

# Snapshot LP assumptions (matches baked frontend defaults).
DEFAULT_LP_RATES = {
    "Minmatar": 850.0,
    "Caldari": 925.0,
    "Amarr": 1000.0,
    "Gallente": 1000.0,
}

CUTS_APPLIED = (
    "Removed Dragoon, Thrasher, Omen, Maller, Breacher. Also cut any line "
    "under 25M on the x100: Tristan, Algos, Catalyst NI, Exequror NI, "
    "Vexor, Vexor NI."
)

# Talwar FI: local SDE may lack BP; BOM matches other navy destroyers.
TALWAR_FI_TYPE_ID = 91858
TALWAR_FI_BPC_TYPE_ID = 91862
TALWAR_FI_BOM_PROXY_TYPE_ID = 73796  # Catalyst Navy Issue

# Full guide catalog (pre-filter). Kept rows are those with orderProfit >= min.
GUIDE_HULL_CANDIDATES: Tuple[Dict[str, Any], ...] = (
    {
        "name": "Caldari Navy Hookbill",
        "type_id": 17619,
        "kind": "Navy",
        "faction": "Caldari",
    },
    {
        "name": "Federation Navy Comet",
        "type_id": 17841,
        "kind": "Navy",
        "faction": "Gallente",
    },
    {
        "name": "Imperial Navy Slicer",
        "type_id": 17703,
        "kind": "Navy",
        "faction": "Amarr",
    },
    {
        "name": "Republic Fleet Firetail",
        "type_id": 17812,
        "kind": "Navy",
        "faction": "Minmatar",
    },
    {
        "name": "Vigil Fleet Issue",
        "type_id": 37454,
        "kind": "Navy",
        "faction": "Minmatar",
    },
    {
        "name": "Tristan",
        "type_id": 593,
        "kind": "T1",
        "faction": "T1",
    },
    {
        "name": "Breacher",
        "type_id": 598,
        "kind": "T1",
        "faction": "T1",
    },
    {
        "name": "Catalyst Navy Issue",
        "type_id": 73796,
        "kind": "Navy",
        "faction": "Gallente",
    },
    {
        "name": "Coercer Navy Issue",
        "type_id": 73789,
        "kind": "Navy",
        "faction": "Amarr",
    },
    {
        "name": "Thrasher Fleet Issue",
        "type_id": 73794,
        "kind": "Navy",
        "faction": "Minmatar",
    },
    {
        "name": "Cormorant Navy Issue",
        "type_id": 73795,
        "kind": "Navy",
        "faction": "Caldari",
    },
    {
        "name": "Talwar Fleet Issue",
        "type_id": TALWAR_FI_TYPE_ID,
        "kind": "Navy",
        "faction": "Minmatar",
        "bom_proxy_type_id": TALWAR_FI_BOM_PROXY_TYPE_ID,
        "bpc_type_id": TALWAR_FI_BPC_TYPE_ID,
        "note": "BOM proxied (identical navy destroyer recipe)",
    },
    {
        "name": "Algos",
        "type_id": 32872,
        "kind": "T1",
        "faction": "T1",
    },
    {
        "name": "Thrasher",
        "type_id": 16242,
        "kind": "T1",
        "faction": "T1",
    },
    {
        "name": "Coercer",
        "type_id": 16236,
        "kind": "T1",
        "faction": "T1",
    },
    {
        "name": "Dragoon",
        "type_id": 32874,
        "kind": "T1",
        "faction": "T1",
    },
    {
        "name": "Arbitrator",
        "type_id": 628,
        "kind": "T1",
        "faction": "T1",
    },
    {
        "name": "Augoror Navy Issue",
        "type_id": 29337,
        "kind": "Navy",
        "faction": "Amarr",
    },
    {
        "name": "Maller",
        "type_id": 624,
        "kind": "T1",
        "faction": "T1",
    },
    {
        "name": "Omen",
        "type_id": 2006,
        "kind": "T1",
        "faction": "T1",
    },
    {
        "name": "Omen Navy Issue",
        "type_id": 17709,
        "kind": "Navy",
        "faction": "Amarr",
    },
    {
        "name": "Caracal Navy Issue",
        "type_id": 17634,
        "kind": "Navy",
        "faction": "Caldari",
    },
    {
        "name": "Osprey Navy Issue",
        "type_id": 29340,
        "kind": "Navy",
        "faction": "Caldari",
    },
    {
        "name": "Exequror Navy Issue",
        "type_id": 29344,
        "kind": "Navy",
        "faction": "Gallente",
    },
    {
        "name": "Vexor",
        "type_id": 627,
        "kind": "T1",
        "faction": "T1",
    },
    {
        "name": "Vexor Navy Issue",
        "type_id": 17843,
        "kind": "Navy",
        "faction": "Gallente",
    },
    {
        "name": "Bellicose",
        "type_id": 630,
        "kind": "T1",
        "faction": "T1",
    },
    {
        "name": "Scythe Fleet Issue",
        "type_id": 29336,
        "kind": "Navy",
        "faction": "Minmatar",
    },
    {
        "name": "Stabber",
        "type_id": 622,
        "kind": "T1",
        "faction": "T1",
    },
    {
        "name": "Stabber Fleet Issue",
        "type_id": 17713,
        "kind": "Navy",
        "faction": "Minmatar",
    },
)

# Explicitly cut even if they would pass the profit filter.
EXPLICIT_CUT_TYPE_IDS = frozenset(
    {
        32874,  # Dragoon
        16242,  # Thrasher
        2006,  # Omen
        624,  # Maller
        598,  # Breacher
    }
)


@dataclass
class GuideOrderRow:
    name: str
    type_id: int
    kind: str
    faction: str
    isk_per_lp: Optional[float]
    cost_per: int
    jita_sell: int
    profit_per: int
    order_profit: int
    note: Optional[str] = None


def default_frontend_module_path() -> Path:
    root = Path(settings.BASE_DIR).resolve().parent
    return (
        root
        / "frontend"
        / "app"
        / "src"
        / "data"
        / "industry"
        / "guide-order-summary.ts"
    )


def _isk_per_lp_for_faction(
    faction: str,
    *,
    lp_rates: Dict[str, float],
    use_production_lp: bool,
    corporation_id: Optional[int],
) -> Optional[float]:
    if faction == "T1":
        return None
    if use_production_lp:
        return resolve_isk_per_lp(
            requested=None, corporation_id=corporation_id
        )
    return float(lp_rates.get(faction, 1000.0))


def _plan_product(
    product_type_id: int,
    *,
    quantity: int,
    facility: str,
) -> Any:
    eve_type = EveType.objects.filter(id=product_type_id).first()
    if eve_type is None:
        raise ValueError(f"Unknown product_type_id {product_type_id}")
    me_pct, te_pct = default_blueprint_me_te_percent(eve_type)
    return plan_build(
        eve_type,
        quantity=quantity,
        blueprint_me=me_pct / 100.0,
        blueprint_te=te_pct / 100.0,
        facility=facility,
    )


def _compressed_cost(
    plan,
    *,
    facility: str,
    navy_bpc_isk: int,
) -> int:
    refine = resolve_refine_rate(
        facility,
        character=None,
        use_reprocessing_implants=False,
    )[0]
    materials = {name: qty for _, (name, qty) in plan.leaf_materials.items()}
    ore_plan = build_compressed_ore_plan(
        materials,
        refine_rate=refine,
        reprocessing_tax=get_facility_reprocessing_tax(facility),
    )
    breakdown = build_plan_cost_breakdown(
        plan,
        compressed_ore=ore_plan,
        navy_bpc_isk=navy_bpc_isk,
    )
    return int(breakdown.grand_total_isk)


def _navy_bpc_isk(
    *,
    product_type_id: int,
    bpc_type_id: Optional[int],
    quantity: int,
    isk_per_lp: Optional[float],
) -> Tuple[int, Optional[float], Optional[int]]:
    """Return (navy_bpc_isk, effective_isk_per_lp, corporation_id)."""
    if isk_per_lp is None or float(isk_per_lp) <= 0:
        return 0, None, None

    blueprint_type_id = bpc_type_id
    if blueprint_type_id is None:
        eve_type = EveType.objects.filter(id=product_type_id).first()
        if eve_type is None or not is_faction_navy_hull(eve_type):
            return 0, None, None
        blueprint_type_id = get_blueprint_or_reaction_type_id(eve_type)

    if blueprint_type_id is None:
        return 0, None, None

    offer = get_offer_for_blueprint_type(int(blueprint_type_id))
    corp_id = offer.corporation_id if offer is not None else None
    rate = resolve_isk_per_lp(requested=isk_per_lp, corporation_id=corp_id)
    if rate is None:
        return 0, None, corp_id

    cost = navy_bpc_cost_for_plan(
        int(blueprint_type_id), quantity, float(rate)
    )
    if cost is None:
        return 0, float(rate), corp_id
    return int(cost.total_isk), float(rate), corp_id


def _resolve_requested_isk_per_lp(
    candidate: Dict[str, Any],
    *,
    lp_rates: Dict[str, float],
    use_production_lp: bool,
) -> Optional[float]:
    faction = candidate["faction"]
    if faction == "T1":
        return None
    if not use_production_lp:
        return float(lp_rates.get(faction, 1000.0))

    type_id = int(candidate["type_id"])
    bpc_type_id = candidate.get("bpc_type_id")
    blueprint_type_id = int(bpc_type_id) if bpc_type_id else None
    if blueprint_type_id is None:
        eve_type = EveType.objects.filter(id=type_id).first()
        if eve_type is not None:
            blueprint_type_id = get_blueprint_or_reaction_type_id(eve_type)
    corp_id = None
    if blueprint_type_id is not None:
        offer = get_offer_for_blueprint_type(int(blueprint_type_id))
        corp_id = offer.corporation_id if offer is not None else None
    return _isk_per_lp_for_faction(
        faction,
        lp_rates=lp_rates,
        use_production_lp=True,
        corporation_id=corp_id,
    )


def compute_row(
    candidate: Dict[str, Any],
    *,
    quantity: int = ORDER_QTY,
    facility: str = FACILITY_KEY,
    lp_rates: Optional[Dict[str, float]] = None,
    use_production_lp: bool = False,
    sell_prices: Optional[Dict[int, int]] = None,
) -> GuideOrderRow:
    rates = lp_rates or DEFAULT_LP_RATES
    type_id = int(candidate["type_id"])
    bom_type_id = int(candidate.get("bom_proxy_type_id") or type_id)
    bpc_type_id = candidate.get("bpc_type_id")
    faction = candidate["faction"]

    requested_lp = _resolve_requested_isk_per_lp(
        candidate,
        lp_rates=rates,
        use_production_lp=use_production_lp,
    )
    navy_isk, effective_lp = _navy_bpc_isk(
        product_type_id=type_id,
        bpc_type_id=int(bpc_type_id) if bpc_type_id else None,
        quantity=1,
        isk_per_lp=requested_lp,
    )[:2]

    plan = _plan_product(bom_type_id, quantity=1, facility=facility)
    cost_per = _compressed_cost(plan, facility=facility, navy_bpc_isk=navy_isk)

    prices = sell_prices or jita_sell_prices_by_type_id([type_id])
    jita_sell = int(prices.get(type_id) or 0)
    profit_per = jita_sell - cost_per
    order_profit = profit_per * quantity

    return GuideOrderRow(
        name=str(candidate["name"]),
        type_id=type_id,
        kind=str(candidate["kind"]),
        faction=str(faction),
        isk_per_lp=float(effective_lp) if effective_lp is not None else None,
        cost_per=cost_per,
        jita_sell=jita_sell,
        profit_per=profit_per,
        order_profit=order_profit,
        note=candidate.get("note"),
    )


def compute_kept_rows(
    *,
    quantity: int = ORDER_QTY,
    facility: str = FACILITY_KEY,
    min_order_profit: int = MIN_ORDER_PROFIT_ISK,
    lp_rates: Optional[Dict[str, float]] = None,
    use_production_lp: bool = False,
    candidates: Sequence[Dict[str, Any]] = GUIDE_HULL_CANDIDATES,
) -> List[GuideOrderRow]:
    type_ids = [int(c["type_id"]) for c in candidates]
    sell_prices = jita_sell_prices_by_type_id(type_ids)
    kept: List[GuideOrderRow] = []
    for candidate in candidates:
        type_id = int(candidate["type_id"])
        if type_id in EXPLICIT_CUT_TYPE_IDS:
            continue
        row = compute_row(
            candidate,
            quantity=quantity,
            facility=facility,
            lp_rates=lp_rates,
            use_production_lp=use_production_lp,
            sell_prices=sell_prices,
        )
        if row.order_profit >= min_order_profit:
            kept.append(row)
    return kept


def _ts_number(n: int) -> str:
    return f"{n:_}"


def _format_as_of(d: date) -> str:
    # e.g. 22 Jul 2026
    return d.strftime("%-d %b %Y")


def render_typescript_module(
    rows: Sequence[GuideOrderRow],
    *,
    as_of: Optional[date] = None,
    quantity: int = ORDER_QTY,
    min_order_profit: int = MIN_ORDER_PROFIT_ISK,
    lp_rates: Optional[Dict[str, float]] = None,
) -> str:
    rates = lp_rates or DEFAULT_LP_RATES
    as_of = as_of or date.today()
    as_of_str = _format_as_of(as_of)

    row_blocks = []
    for r in rows:
        note_line = f",\n        note: {r.note!r}," if r.note else ","
        isk_lp = "null" if r.isk_per_lp is None else str(int(r.isk_per_lp))
        row_blocks.append(f"""    {{
        name: {r.name!r},
        typeId: {r.type_id},
        kind: {r.kind!r},
        faction: {r.faction!r},
        iskPerLp: {isk_lp},
        costPer: {_ts_number(r.cost_per)},
        jitaSell: {_ts_number(r.jita_sell)},
        profitPer: {_ts_number(r.profit_per)},
        orderProfit: {_ts_number(r.order_profit)}{note_line}
    }}""")
    rows_joined = ",\n".join(row_blocks)

    assumptions = (
        "Qty ${ORDER_QTY} per hull. Navy BPCs ME0/TE0 from FW LP store "
        "(Minmatar ${LP_RATES.Minmatar}, Caldari ${LP_RATES.Caldari}, "
        "Amarr ${LP_RATES.Amarr}, Gallente ${LP_RATES.Gallente} ISK/LP). "
        "T1 assumes researched ME10/TE20 BPO (no LP). Amamake Sotiyo + Tatara "
        "compressed-ore shopping, Jita to Amamake freight, revenue = Jita sell "
        "x ${ORDER_QTY} (no broker/sales tax). Talwar FI uses the same navy "
        "destroyer BOM."
    )

    return f"""/**
 * Guide hull manufacturing order summary (static report).
 *
 * Baked from Amamake compressed-ore planner + Jita sell · qty {quantity} · {min_order_profit // 1_000_000}M+ x{quantity} filter.
 * Refresh: `pipenv run python manage.py export_guide_order_summary`
 *
 * As-of: {as_of_str}
 */

export const AS_OF_DATE = {as_of_str!r}
export const ORDER_QTY = {quantity}
export const MIN_ORDER_PROFIT_ISK = {_ts_number(min_order_profit)}
export const FACILITY_KEY = {FACILITY_KEY!r}

/** ISK/LP used when this snapshot was baked (not necessarily live production defaults). */
export const LP_RATES = {{
    Minmatar: {int(rates["Minmatar"])},
    Caldari: {int(rates["Caldari"])},
    Amarr: {int(rates["Amarr"])},
    Gallente: {int(rates["Gallente"])},
}} as const

export type GuideOrderHullKind = 'Navy' | 'T1'
export type GuideOrderFaction =
    | 'Amarr'
    | 'Caldari'
    | 'Gallente'
    | 'Minmatar'
    | 'T1'

export type GuideOrderRow = {{
    name: string
    typeId: number
    kind: GuideOrderHullKind
    faction: GuideOrderFaction
    iskPerLp: number | null
    costPer: number
    jitaSell: number
    profitPer: number
    orderProfit: number
    note?: string
}}

export type GuideOrderTableTone = 'info' | 'success' | 'warning' | 'danger'

export type GuideOrderTableRow = {{
    cells: readonly string[]
    tone?: GuideOrderTableTone
}}

/** Kept lines only (explicit cuts + under {min_order_profit // 1_000_000}M x{quantity} removed). */
export const GUIDE_ORDER_ROWS: readonly GuideOrderRow[] = [
{rows_joined},
]

export const CUTS_APPLIED =
    {CUTS_APPLIED!r}

export const ASSUMPTIONS_TEXT =
    `{assumptions}`

export function formatIskCompact(isk: number): string {{
    const abs = Math.abs(isk)
    const sign = isk < 0 ? '-' : ''
    if (abs >= 1_000_000_000) {{
        return `${{sign}}${{(abs / 1_000_000_000).toFixed(2)}}B`
    }}
    if (abs >= 1_000_000) {{
        return `${{sign}}${{(abs / 1_000_000).toFixed(2)}}M`
    }}
    if (abs >= 1_000) {{
        return `${{sign}}${{(abs / 1_000).toFixed(0)}}k`
    }}
    return `${{sign}}${{abs.toFixed(0)}}`
}}

export function formatIskFull(isk: number): string {{
    return Math.round(isk).toLocaleString('en-US')
}}

export function shortHullName(name: string): string {{
    return name
        .replace(' Navy Issue', ' NI')
        .replace(' Fleet Issue', ' FI')
        .replace('Caldari Navy ', '')
        .replace('Federation Navy ', '')
        .replace('Imperial Navy ', '')
        .replace('Republic Fleet ', '')
}}

export function rowTone(orderProfit: number): GuideOrderTableTone {{
    if (orderProfit >= 100_000_000) return 'success'
    if (orderProfit >= MIN_ORDER_PROFIT_ISK) return 'info'
    return 'danger'
}}

export function sortedByOrderProfit(
    rows: readonly GuideOrderRow[] = GUIDE_ORDER_ROWS,
): GuideOrderRow[] {{
    return [...rows].sort((a, b) => b.orderProfit - a.orderProfit)
}}

export function orderTotals(rows: readonly GuideOrderRow[] = GUIDE_ORDER_ROWS) {{
    const totalProfit = rows.reduce((sum, r) => sum + r.orderProfit, 0)
    const navyRows = rows.filter((r) => r.kind === 'Navy')
    const t1Rows = rows.filter((r) => r.kind === 'T1')
    const sorted = sortedByOrderProfit(rows)
    return {{
        totalProfit,
        hullCount: rows.length,
        navyCount: navyRows.length,
        t1Count: t1Rows.length,
        navyProfit: navyRows.reduce((sum, r) => sum + r.orderProfit, 0),
        t1Profit: t1Rows.reduce((sum, r) => sum + r.orderProfit, 0),
        best: sorted[0],
        worst: sorted[sorted.length - 1],
        sorted,
    }}
}}

export function keptOrderTableRows(
    rows: readonly GuideOrderRow[] = GUIDE_ORDER_ROWS,
): GuideOrderTableRow[] {{
    return rows.map((r) => ({{
        cells: [
            r.note ? `${{r.name}}*` : r.name,
            r.iskPerLp == null ? '-' : String(r.iskPerLp),
            formatIskCompact(r.costPer),
            formatIskCompact(r.jitaSell),
            formatIskFull(r.profitPer),
            formatIskCompact(r.orderProfit),
        ] as const,
        tone: rowTone(r.orderProfit),
    }}))
}}
"""


def write_frontend_module(
    rows: Sequence[GuideOrderRow],
    *,
    path: Optional[Path] = None,
    as_of: Optional[date] = None,
    quantity: int = ORDER_QTY,
    min_order_profit: int = MIN_ORDER_PROFIT_ISK,
    lp_rates: Optional[Dict[str, float]] = None,
) -> Path:
    out = path or default_frontend_module_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    content = render_typescript_module(
        rows,
        as_of=as_of,
        quantity=quantity,
        min_order_profit=min_order_profit,
        lp_rates=lp_rates,
    )
    out.write_text(content, encoding="utf-8")
    return out
