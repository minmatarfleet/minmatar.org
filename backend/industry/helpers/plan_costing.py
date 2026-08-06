"""
Unified industry plan costing (Pydantic public API).

Every ISK consumer (planner, profit summary, guide export, LP conversion)
should call ``plan_item_cost`` / ``plan_lp_offer_conversion`` rather than
assembling ``build_plan_cost_breakdown`` ad hoc.

Freight defaults:
  - Planner / profit / guide: alliance hub→facility route (ISK/m³ + collateral)
  - LP conversion: Red Frog value % (45M ISK per 1.5B cargo) on Jita ↔ Amo
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple, Union

from pydantic import BaseModel, Field
from eveuniverse.models import EveType

from industry.helpers.blueprint_efficiency import (
    default_blueprint_me_te_percent,
    is_faction_navy_hull,
)
from industry.helpers.build_planner import BuildPlan, plan_build
from industry.helpers.compressed_ore import (
    CompressedOrePlan,
    build_compressed_ore_plan,
)
from industry.helpers.cost_breakdown import (
    materials_jita_sell_isk_from_named,
    materials_jita_sell_isk_from_type_qtys,
    reprocessing_output_value_isk,
    jita_sell_prices_by_type_id,
    _prices_by_name,
)
from industry.helpers.facility_profiles import get_facility_reprocessing_tax
from industry.helpers.freight_costs import (
    FreightEstimate,
    estimate_plan_freight,
)
from industry.helpers.loyalty_store import (
    get_offer_for_blueprint_type,
    navy_bpc_cost_for_plan,
    resolve_isk_per_lp,
)
from industry.helpers.reprocessing_skills import resolve_refine_rate
from industry.helpers.type_breakdown import (
    ACTIVITY_REACTION,
    get_blueprint_or_reaction_type_id,
)

# Red Frog quote: 45M ISK per 1.5B cargo value → 3%.
RED_FROG_VALUE_RATE = 45_000_000 / 1_500_000_000
RED_FROG_LABEL = "Red Frog Freight"
RED_FROG_ROUTE_LABEL = "Jita ↔ Amo"

# Accounting V sales tax (no broker fee).
DEFAULT_SALES_TAX_RATE = 0.0337

DEFAULT_FACILITY_KEY = "amamake"

# Talwar FI: local SDE may lack BP; BOM matches other navy destroyers.
TALWAR_FI_TYPE_ID = 91858
TALWAR_FI_BPC_TYPE_ID = 91862
TALWAR_FI_BOM_PROXY_TYPE_ID = 73796  # Catalyst Navy Issue


class FreightMode(str, Enum):
    # Lowercase members match freight option API strings.
    off = "off"  # pylint: disable=invalid-name
    alliance_route = "alliance_route"  # pylint: disable=invalid-name
    value_percent = "value_percent"  # pylint: disable=invalid-name


class FreightOptions(BaseModel):
    """How to price inbound (or outbound) freight for a plan."""

    mode: FreightMode = FreightMode.alliance_route
    value_rate: float = Field(
        default=RED_FROG_VALUE_RATE,
        description="Fraction of cargo ISK (45M / 1.5B for Red Frog).",
    )
    value_label: str = Field(
        default=RED_FROG_LABEL,
        description="Carrier / quote label for value_percent mode.",
    )
    route_label: str = Field(
        default=RED_FROG_ROUTE_LABEL,
        description="Route label for value_percent mode (e.g. Jita ↔ Amo).",
    )
    alliance_facility_key: Optional[str] = Field(
        default=None,
        description=(
            "Facility key for alliance_route lookup. "
            "Defaults to the plan facility when unset."
        ),
    )

    @classmethod
    def off(cls) -> "FreightOptions":
        return cls(mode=FreightMode.off)

    @classmethod
    def alliance_default(cls) -> "FreightOptions":
        return cls(mode=FreightMode.alliance_route)

    @classmethod
    def red_frog_jita_amo(cls) -> "FreightOptions":
        return cls(
            mode=FreightMode.value_percent,
            value_rate=RED_FROG_VALUE_RATE,
            value_label=RED_FROG_LABEL,
            route_label=RED_FROG_ROUTE_LABEL,
        )


class SalesTaxOptions(BaseModel):
    enabled: bool = True
    rate: float = Field(
        default=DEFAULT_SALES_TAX_RATE,
        description="Sales tax fraction of revenue (Accounting V = 3.37%).",
    )

    @classmethod
    def off(cls) -> "SalesTaxOptions":
        return cls(enabled=False, rate=0.0)

    @classmethod
    def accounting_v(cls) -> "SalesTaxOptions":
        return cls(enabled=True, rate=DEFAULT_SALES_TAX_RATE)


class PlanCostOptions(BaseModel):
    """Knobs for ``plan_item_cost``."""

    facility: str = DEFAULT_FACILITY_KEY
    quantity: int = 1
    compressed: bool = True
    blueprint_me: Optional[float] = None
    blueprint_te: Optional[float] = None
    build_fuel_blocks: bool = False
    exclude_type_ids: List[int] = Field(default_factory=list)
    include_navy_bpc: bool = True
    isk_per_lp: Optional[float] = None
    use_production_lp: bool = True
    input_freight: FreightOptions = Field(
        default_factory=FreightOptions.alliance_default
    )
    # Output freight is applied by ``plan_lp_offer_conversion`` on revenue.
    output_freight: FreightOptions = Field(default_factory=FreightOptions.off)
    sales_tax: SalesTaxOptions = Field(default_factory=SalesTaxOptions.off)
    include_line_items: bool = True
    use_reprocessing_implants: bool = False
    refine_rate_override: Optional[float] = None

    @classmethod
    def planner_defaults(cls, **kwargs) -> "PlanCostOptions":
        """Interactive planner / profit / guide: alliance inbound freight."""
        return cls(
            input_freight=FreightOptions.alliance_default(),
            output_freight=FreightOptions.off(),
            sales_tax=SalesTaxOptions.off(),
            **kwargs,
        )

    @classmethod
    def lp_conversion_defaults(cls, **kwargs) -> "PlanCostOptions":
        """LP store net: Red Frog value freight; no alliance route."""
        return cls(
            input_freight=FreightOptions.red_frog_jita_amo(),
            output_freight=FreightOptions.red_frog_jita_amo(),
            sales_tax=SalesTaxOptions.accounting_v(),
            include_navy_bpc=False,
            **kwargs,
        )


class CostLineItemModel(BaseModel):
    key: str
    label: str
    amount_isk: int


class FreightCost(BaseModel):
    isk: int = 0
    mode: FreightMode = FreightMode.off
    rate: Optional[float] = None
    basis_isk: int = 0
    label: str = ""
    route_label: Optional[str] = None
    volume_m3: float = 0.0
    billable_m3: int = 0
    route_id: Optional[int] = None
    has_route: bool = False


class ItemPlanCost(BaseModel):
    """Full build cost for one product lot."""

    type_id: int
    name: str
    kind: str = ""  # "Navy" | "T1" | ""
    output_quantity: int = 1
    materials_jita_sell_isk: int = 0
    manufacturing_job_costs_isk: int = 0
    reaction_job_costs_isk: int = 0
    total_job_costs_isk: int = 0
    facility_tax_isk: int = 0
    scc_tax_isk: int = 0
    reprocessing_tax_isk: int = 0
    taxes_isk: int = 0
    navy_bpc_isk: int = 0
    input_freight: FreightCost = Field(default_factory=FreightCost)
    # Materials + jobs + taxes + input freight (excludes navy BPC).
    manufacturing_isk: int = 0
    grand_total_isk: int = 0
    per_unit_isk: float = 0.0
    manufacturing_cost_per_isk: int = 0
    cost_per_isk: int = 0
    jita_sell_isk: int = 0
    profit_per_isk: int = 0
    isk_per_lp: Optional[float] = None
    note: Optional[str] = None
    line_items: List[CostLineItemModel] = Field(default_factory=list)
    facility: str = DEFAULT_FACILITY_KEY

    def to_legacy_breakdown_dict(self) -> dict:
        """Shape expected by planner ``PlanCostBreakdownSchema`` / UI."""
        freight = self.input_freight
        return {
            "materials_jita_sell_isk": self.materials_jita_sell_isk,
            "manufacturing_job_costs_isk": self.manufacturing_job_costs_isk,
            "reaction_job_costs_isk": self.reaction_job_costs_isk,
            "total_job_costs_isk": self.total_job_costs_isk,
            "facility_tax_isk": self.facility_tax_isk,
            "scc_tax_isk": self.scc_tax_isk,
            "reprocessing_tax_isk": self.reprocessing_tax_isk,
            "taxes_isk": self.taxes_isk,
            "freight_isk": freight.isk,
            "freight_volume_m3": freight.volume_m3,
            "freight_billable_m3": freight.billable_m3,
            "freight_route_id": freight.route_id,
            "freight_route_label": freight.route_label,
            "navy_bpc_isk": self.navy_bpc_isk,
            "grand_total_isk": self.grand_total_isk,
            "per_unit_isk": self.per_unit_isk,
            "output_quantity": self.output_quantity,
            "line_items": [
                {
                    "key": item.key,
                    "label": item.label,
                    "amount_isk": item.amount_isk,
                }
                for item in self.line_items
            ],
        }


class LpOfferConversion(BaseModel):
    """Net ISK/LP conversion for one LP store offer side."""

    lp_cost: int
    isk_cost: int
    quantity: int
    market_price_isk: Optional[int] = None
    market_side: str = "sell"
    revenue_isk: Optional[int] = None
    required_items_isk: int = 0
    build_materials_isk: int = 0
    build_manufacturing_isk: int = 0
    input_isk: int = 0
    input_freight: FreightCost = Field(default_factory=FreightCost)
    output_freight: FreightCost = Field(default_factory=FreightCost)
    sales_tax_isk: int = 0
    sales_tax_rate: float = 0.0
    raw_isk_per_lp: Optional[float] = None
    input_isk_per_lp: Optional[float] = None
    sales_tax_isk_per_lp: Optional[float] = None
    input_freight_isk_per_lp: Optional[float] = None
    output_freight_isk_per_lp: Optional[float] = None
    net_isk_per_lp: Optional[float] = None


def bom_and_bpc_overrides(
    type_id: int,
) -> Tuple[int, Optional[int], Optional[str]]:
    """Return (bom_type_id, bpc_type_id, note) for known SDE gaps."""
    if int(type_id) == TALWAR_FI_TYPE_ID:
        return (
            TALWAR_FI_BOM_PROXY_TYPE_ID,
            TALWAR_FI_BPC_TYPE_ID,
            "BOM proxied (identical navy destroyer recipe)",
        )
    return int(type_id), None, None


def _value_percent_freight(
    *,
    basis_isk: int,
    options: FreightOptions,
    volume_m3: float = 0.0,
    billable_m3: int = 0,
) -> FreightCost:
    basis = max(0, int(basis_isk))
    rate = float(options.value_rate)
    isk = int(math.ceil(rate * basis)) if basis > 0 and rate > 0 else 0
    label = options.value_label
    if options.route_label:
        label = f"{options.value_label} ({options.route_label})"
    return FreightCost(
        isk=isk,
        mode=FreightMode.value_percent,
        rate=rate,
        basis_isk=basis,
        label=label,
        route_label=options.route_label,
        volume_m3=float(volume_m3),
        billable_m3=int(billable_m3),
        has_route=True,
    )


def _alliance_freight_from_estimate(
    estimate: FreightEstimate,
    *,
    basis_isk: int,
) -> FreightCost:
    label = "Freight"
    if estimate.route_label:
        label = f"Freight ({estimate.route_label})"
    return FreightCost(
        isk=int(estimate.freight_isk),
        mode=FreightMode.alliance_route,
        rate=None,
        basis_isk=max(0, int(basis_isk)),
        label=label,
        route_label=estimate.route_label,
        volume_m3=float(estimate.volume_m3),
        billable_m3=int(estimate.billable_m3),
        route_id=estimate.route_id,
        has_route=estimate.has_route,
    )


def _resolve_input_freight(
    *,
    options: FreightOptions,
    facility_key: str,
    materials_isk: int,
    type_qtys: Optional[Sequence[Tuple[int, int]]],
    named_qtys: Optional[Dict[str, int]],
) -> FreightCost:
    if options.mode == FreightMode.off:
        return FreightCost(mode=FreightMode.off, label="Freight (off)")
    if options.mode == FreightMode.value_percent:
        estimate = estimate_plan_freight(
            facility_key=facility_key,
            type_qtys=type_qtys,
            named_qtys=named_qtys,
            collateral_isk=materials_isk,
        )
        return _value_percent_freight(
            basis_isk=materials_isk,
            options=options,
            volume_m3=estimate.volume_m3,
            billable_m3=estimate.billable_m3,
        )
    # alliance_route
    key = options.alliance_facility_key or facility_key
    estimate = estimate_plan_freight(
        facility_key=key,
        type_qtys=type_qtys,
        named_qtys=named_qtys,
        collateral_isk=materials_isk,
    )
    return _alliance_freight_from_estimate(estimate, basis_isk=materials_isk)


def _job_tax_totals(plan: BuildPlan) -> Tuple[int, int, int, int]:
    mfg_gross = 0
    rxn_gross = 0
    facility_tax_isk = 0
    scc_tax_isk = 0
    for job in plan.jobs:
        facility_tax_isk += job.job_cost.facility_tax_isk
        scc_tax_isk += job.job_cost.scc_tax_isk
        if job.activity_id == ACTIVITY_REACTION:
            rxn_gross += job.job_cost.gross_cost
        else:
            mfg_gross += job.job_cost.gross_cost
    return mfg_gross, rxn_gross, facility_tax_isk, scc_tax_isk


def cost_build_plan(
    plan: BuildPlan,
    *,
    compressed_ore: Optional[CompressedOrePlan] = None,
    navy_bpc_isk: int = 0,
    input_freight: Optional[FreightOptions] = None,
    include_line_items: bool = True,
    type_id: Optional[int] = None,
    name: Optional[str] = None,
    kind: str = "",
    jita_sell_isk: int = 0,
    isk_per_lp: Optional[float] = None,
    note: Optional[str] = None,
) -> ItemPlanCost:
    """
    Cost an existing ``BuildPlan`` (+ optional compressed Multibuy).

    This is the shared core used by ``plan_item_cost`` and the planner
    endpoint (which already has a ``BuildPlan``).
    """
    freight_opts = input_freight or FreightOptions.alliance_default()
    mfg_gross, rxn_gross, facility_tax_isk, scc_tax_isk = _job_tax_totals(plan)
    total_job_costs = mfg_gross + rxn_gross
    navy = max(int(navy_bpc_isk), 0)

    type_qtys: Optional[List[Tuple[int, int]]] = None
    named_qtys: Optional[Dict[str, int]] = None
    if compressed_ore is not None:
        import_map = dict(compressed_ore.import_lines())
        named_qtys = import_map
        names = (
            set(import_map)
            | set(compressed_ore.expected_minerals)
            | set(compressed_ore.expected_ice_products)
        )
        prices_by_name = _prices_by_name(names)
        materials_isk = materials_jita_sell_isk_from_named(
            import_map, prices_by_name=prices_by_name
        )
        output_value = reprocessing_output_value_isk(
            compressed_ore, prices_by_name=prices_by_name
        )
        reprocessing_tax_isk = compressed_ore.tax_isk(float(output_value))
    else:
        type_qtys = [
            (tid, qty) for tid, (_, qty) in plan.leaf_materials.items()
        ]
        materials_isk = materials_jita_sell_isk_from_type_qtys(type_qtys)
        reprocessing_tax_isk = 0

    taxes_isk = facility_tax_isk + scc_tax_isk + reprocessing_tax_isk
    freight = _resolve_input_freight(
        options=freight_opts,
        facility_key=plan.facility_key,
        materials_isk=materials_isk,
        type_qtys=type_qtys,
        named_qtys=named_qtys,
    )

    manufacturing_isk = (
        materials_isk + total_job_costs + taxes_isk + freight.isk
    )
    grand_total = manufacturing_isk + navy
    output_qty = max(int(plan.quantity), 1)
    per_unit = grand_total / output_qty
    cost_per = int(round(grand_total / output_qty))
    mfg_per = int(round(manufacturing_isk / output_qty))

    line_items: List[CostLineItemModel] = []
    if include_line_items:
        line_items = [
            CostLineItemModel(
                key="materials_jita_sell",
                label="Materials",
                amount_isk=materials_isk,
            ),
            CostLineItemModel(
                key="manufacturing_job_costs",
                label="Manufacturing job install",
                amount_isk=mfg_gross,
            ),
            CostLineItemModel(
                key="reaction_job_costs",
                label="Reaction job install",
                amount_isk=rxn_gross,
            ),
            CostLineItemModel(
                key="facility_tax",
                label="Facility tax",
                amount_isk=facility_tax_isk,
            ),
            CostLineItemModel(
                key="scc_tax",
                label="SCC surcharge",
                amount_isk=scc_tax_isk,
            ),
        ]
        if compressed_ore is not None:
            line_items.append(
                CostLineItemModel(
                    key="reprocessing_tax",
                    label="Reprocessing tax",
                    amount_isk=reprocessing_tax_isk,
                )
            )
        if freight.mode == FreightMode.alliance_route and freight.has_route:
            line_items.append(
                CostLineItemModel(
                    key="freight",
                    label=freight.label or "Freight",
                    amount_isk=freight.isk,
                )
            )
        elif freight.mode == FreightMode.value_percent and freight.isk > 0:
            line_items.append(
                CostLineItemModel(
                    key="freight",
                    label=freight.label or "Freight",
                    amount_isk=freight.isk,
                )
            )
        if navy > 0:
            line_items.append(
                CostLineItemModel(
                    key="navy_bpc_lp",
                    label="Navy BPC (LP)",
                    amount_isk=navy,
                )
            )

    resolved_type_id = int(
        type_id if type_id is not None else plan.product_type_id
    )
    resolved_name = name or plan.product_name or str(resolved_type_id)

    return ItemPlanCost(
        type_id=resolved_type_id,
        name=resolved_name,
        kind=kind,
        output_quantity=output_qty,
        materials_jita_sell_isk=materials_isk,
        manufacturing_job_costs_isk=mfg_gross,
        reaction_job_costs_isk=rxn_gross,
        total_job_costs_isk=total_job_costs,
        facility_tax_isk=facility_tax_isk,
        scc_tax_isk=scc_tax_isk,
        reprocessing_tax_isk=reprocessing_tax_isk,
        taxes_isk=taxes_isk,
        navy_bpc_isk=navy,
        input_freight=freight,
        manufacturing_isk=manufacturing_isk,
        grand_total_isk=grand_total,
        per_unit_isk=per_unit,
        manufacturing_cost_per_isk=mfg_per,
        cost_per_isk=cost_per,
        jita_sell_isk=int(jita_sell_isk),
        profit_per_isk=int(jita_sell_isk) - cost_per,
        isk_per_lp=isk_per_lp,
        note=note,
        line_items=line_items,
        facility=plan.facility_key,
    )


def navy_bpc_isk_for_product(
    *,
    product_type_id: int,
    bpc_type_id: Optional[int],
    quantity: int,
    isk_per_lp: Optional[float],
) -> Tuple[int, Optional[float]]:
    """Return (navy_bpc_isk, effective_isk_per_lp)."""
    blueprint_type_id = bpc_type_id
    if blueprint_type_id is None:
        eve_type = EveType.objects.filter(id=product_type_id).first()
        if eve_type is None or not is_faction_navy_hull(eve_type):
            return 0, None
        blueprint_type_id = get_blueprint_or_reaction_type_id(eve_type)

    if blueprint_type_id is None:
        return 0, None

    offer = get_offer_for_blueprint_type(int(blueprint_type_id))
    corp_id = offer.corporation_id if offer is not None else None
    rate = resolve_isk_per_lp(requested=isk_per_lp, corporation_id=corp_id)
    if rate is None:
        return 0, None

    cost = navy_bpc_cost_for_plan(
        int(blueprint_type_id), quantity, float(rate)
    )
    if cost is None:
        return 0, float(rate)
    return int(cost.total_isk), float(rate)


def resolve_production_isk_per_lp(
    product_type_id: int,
    *,
    bpc_type_id: Optional[int] = None,
) -> Optional[float]:
    blueprint_type_id = bpc_type_id
    if blueprint_type_id is None:
        eve_type = EveType.objects.filter(id=product_type_id).first()
        if eve_type is None:
            return None
        blueprint_type_id = get_blueprint_or_reaction_type_id(eve_type)
    if blueprint_type_id is None:
        return None
    offer = get_offer_for_blueprint_type(int(blueprint_type_id))
    corp_id = offer.corporation_id if offer is not None else None
    return resolve_isk_per_lp(requested=None, corporation_id=corp_id)


def plan_item_cost(
    type_id: Union[int, EveType],
    options: Optional[PlanCostOptions] = None,
    *,
    sell_prices: Optional[Dict[int, int]] = None,
) -> ItemPlanCost:
    """
    Plan and cost one product lot.

    Public entry point for planner-style unit costs, profit summaries,
    and guide export.
    """
    opts = options or PlanCostOptions.planner_defaults()
    if isinstance(type_id, EveType):
        eve_type = type_id
        resolved_id = int(eve_type.id)
    else:
        resolved_id = int(type_id)
        eve_type = EveType.objects.filter(id=resolved_id).first()
        if eve_type is None:
            raise ValueError(f"Unknown product_type_id {resolved_id}")

    batch = max(int(opts.quantity), 1)
    bom_type_id, bpc_override, note = bom_and_bpc_overrides(resolved_id)
    is_navy = is_faction_navy_hull(eve_type)
    kind = "Navy" if is_navy else "T1"

    if bom_type_id != resolved_id:
        bom_eve = EveType.objects.filter(id=bom_type_id).first()
        if bom_eve is None:
            raise ValueError(f"Unknown BOM product_type_id {bom_type_id}")
        plan_eve = bom_eve
    else:
        plan_eve = eve_type

    # default_blueprint_me_te_percent returns percent; plan_build wants fraction.
    # PlanCostOptions.blueprint_me/te are fractions (same as plan_build).
    default_me, default_te = default_blueprint_me_te_percent(plan_eve)
    me = (
        float(opts.blueprint_me)
        if opts.blueprint_me is not None
        else default_me / 100.0
    )
    te = (
        float(opts.blueprint_te)
        if opts.blueprint_te is not None
        else default_te / 100.0
    )

    plan = plan_build(
        plan_eve,
        quantity=batch,
        blueprint_me=me,
        blueprint_te=te,
        facility=opts.facility,
        build_fuel_blocks=opts.build_fuel_blocks,
        exclude_type_ids=list(opts.exclude_type_ids or []),
    )

    requested_lp: Optional[float] = None
    navy_isk = 0
    effective_lp: Optional[float] = None
    if opts.include_navy_bpc and is_navy:
        if opts.isk_per_lp is not None and float(opts.isk_per_lp) > 0:
            requested_lp = float(opts.isk_per_lp)
        elif opts.use_production_lp:
            requested_lp = resolve_production_isk_per_lp(
                resolved_id, bpc_type_id=bpc_override
            )
        navy_isk, effective_lp = navy_bpc_isk_for_product(
            product_type_id=resolved_id,
            bpc_type_id=bpc_override,
            quantity=batch,
            isk_per_lp=requested_lp,
        )

    ore_plan: Optional[CompressedOrePlan] = None
    if opts.compressed:
        refine = resolve_refine_rate(
            opts.facility,
            character=None,
            use_reprocessing_implants=opts.use_reprocessing_implants,
            refine_rate_override=opts.refine_rate_override,
        )[0]
        materials = {
            name: qty for _, (name, qty) in plan.leaf_materials.items()
        }
        ore_plan = build_compressed_ore_plan(
            materials,
            refine_rate=refine,
            reprocessing_tax=get_facility_reprocessing_tax(opts.facility),
        )

    prices = sell_prices or jita_sell_prices_by_type_id([resolved_id])
    jita_sell = int(prices.get(resolved_id) or 0)

    return cost_build_plan(
        plan,
        compressed_ore=ore_plan,
        navy_bpc_isk=navy_isk,
        input_freight=opts.input_freight,
        include_line_items=opts.include_line_items,
        type_id=resolved_id,
        name=eve_type.name or str(resolved_id),
        kind=kind,
        jita_sell_isk=jita_sell,
        isk_per_lp=effective_lp if is_navy else None,
        note=note,
    )


def _apply_freight_options(
    *,
    basis_isk: int,
    options: FreightOptions,
) -> FreightCost:
    if options.mode == FreightMode.off:
        return FreightCost(mode=FreightMode.off, label="Freight (off)")
    if options.mode == FreightMode.value_percent:
        return _value_percent_freight(basis_isk=basis_isk, options=options)
    # alliance_route on a pure ISK basis is not volume-priced; treat as off
    # unless callers supply volume via cost_build_plan.
    return FreightCost(
        mode=FreightMode.alliance_route,
        basis_isk=max(0, int(basis_isk)),
        label="Freight (alliance requires volume)",
        has_route=False,
    )


def plan_lp_offer_conversion(
    *,
    lp_cost: int,
    isk_cost: int,
    quantity: int,
    market_price_isk: Optional[int],
    required_items_isk: int = 0,
    build_plan: Optional[ItemPlanCost] = None,
    input_freight: Optional[FreightOptions] = None,
    output_freight: Optional[FreightOptions] = None,
    sales_tax: Optional[SalesTaxOptions] = None,
    market_side: str = "sell",
) -> LpOfferConversion:
    """
    Net ISK/LP for an LP store offer.

    ``build_plan`` should be priced with alliance freight **off** (materials
    + jobs + taxes only). Input freight uses Red Frog % on
    required items + materials; output freight and sales tax apply to revenue.
    """
    in_freight_opts = input_freight or FreightOptions.red_frog_jita_amo()
    out_freight_opts = output_freight or FreightOptions.red_frog_jita_amo()
    tax_opts = sales_tax or SalesTaxOptions.accounting_v()

    qty = max(int(quantity), 1)
    lp = int(lp_cost)
    required = max(0, int(required_items_isk))
    materials = int(build_plan.materials_jita_sell_isk) if build_plan else 0
    # Manufacturing excl. navy BPC and excl. any freight already on the plan.
    if build_plan is not None:
        build_mfg = (
            int(build_plan.materials_jita_sell_isk)
            + int(build_plan.total_job_costs_isk)
            + int(build_plan.taxes_isk)
        )
    else:
        build_mfg = 0

    input_isk = int(isk_cost) + required + build_mfg
    freight_basis = required + materials
    input_freight_cost = _apply_freight_options(
        basis_isk=freight_basis, options=in_freight_opts
    )

    revenue: Optional[int] = None
    sales_tax_isk = 0
    output_freight_cost = FreightCost(mode=out_freight_opts.mode)
    if market_price_isk is not None:
        revenue = int(market_price_isk) * qty
        if tax_opts.enabled and tax_opts.rate > 0:
            sales_tax_isk = int(math.ceil(float(tax_opts.rate) * revenue))
        output_freight_cost = _apply_freight_options(
            basis_isk=revenue, options=out_freight_opts
        )

    def per_lp(amount: Optional[int]) -> Optional[float]:
        if amount is None or lp <= 0:
            return None
        return float(amount) / float(lp)

    raw = per_lp(revenue)
    input_rate = per_lp(input_isk)
    tax_rate = per_lp(sales_tax_isk) if revenue is not None else None
    in_f_rate = per_lp(input_freight_cost.isk)
    out_f_rate = (
        per_lp(output_freight_cost.isk) if revenue is not None else None
    )

    net: Optional[float] = None
    if revenue is not None and lp > 0:
        net_isk = (
            revenue
            - sales_tax_isk
            - input_isk
            - input_freight_cost.isk
            - output_freight_cost.isk
        )
        net = float(net_isk) / float(lp)

    return LpOfferConversion(
        lp_cost=lp,
        isk_cost=int(isk_cost),
        quantity=qty,
        market_price_isk=market_price_isk,
        market_side=market_side,
        revenue_isk=revenue,
        required_items_isk=required,
        build_materials_isk=materials,
        build_manufacturing_isk=build_mfg,
        input_isk=input_isk,
        input_freight=input_freight_cost,
        output_freight=output_freight_cost,
        sales_tax_isk=sales_tax_isk,
        sales_tax_rate=float(tax_opts.rate) if tax_opts.enabled else 0.0,
        raw_isk_per_lp=raw,
        input_isk_per_lp=input_rate,
        sales_tax_isk_per_lp=tax_rate,
        input_freight_isk_per_lp=in_f_rate,
        output_freight_isk_per_lp=out_f_rate,
        net_isk_per_lp=net,
    )
