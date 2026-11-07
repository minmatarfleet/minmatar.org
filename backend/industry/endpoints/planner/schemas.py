"""Schemas for industry planner endpoints."""

from __future__ import annotations

from typing import Dict, List, Optional

from ninja import Schema


class FacilityFittingPieceSchema(Schema):
    name: str
    type_id: int
    effects: List[str]
    job_class: Optional[str] = None


class FacilityStructureSchema(Schema):
    role: str
    name: str
    kind: str
    type_id: int
    effects: List[str]
    rigs: List[FacilityFittingPieceSchema]


class FacilityReprocessingSchema(Schema):
    structure_name: str
    structure_type_id: int
    rig_name: str
    rig_type_id: int
    facility_base_yield: float
    refine_rate: float
    facility_tax: float
    effects: List[str]


class FacilitySummarySchema(Schema):
    key: str
    system_id: int
    system_name: str
    structures: List[FacilityStructureSchema]
    system_cost_bonus: float
    facility_tax: float
    scc_surcharge: float
    reprocessing: FacilityReprocessingSchema


class JobClassBonusSchema(Schema):
    job_class: str
    structure_name: str
    structure_type_id: int
    rig_name: str
    rig_type_id: int
    role_me: float
    role_te: float
    rig_me: float
    rig_te: float
    structure_isk_bonus: float
    effects: List[str]


class CostIndicesSchema(Schema):
    manufacturing: float
    reaction: float
    # Science indices (invention + copying). Omitted where not looked up.
    invention: Optional[float] = None
    copying: Optional[float] = None


class FacilityDetailSchema(FacilitySummarySchema):
    job_classes: List[JobClassBonusSchema]
    cost_indices: CostIndicesSchema
    indices_from_esi: bool


class SystemIndustrySchema(Schema):
    system_id: int
    system_name: str
    facility_key: Optional[str] = None
    facility: Optional[FacilitySummarySchema] = None
    cost_indices: CostIndicesSchema
    indices_from_esi: bool


class PlanInventionSkillsSchema(Schema):
    science_1: int = 5
    science_2: int = 5
    encryption: int = 4


class PlanRequestSchema(Schema):
    product_type_id: int
    quantity: int = 1
    # Omit for product-aware defaults (10/20, or 0/0 for faction/navy hulls).
    blueprint_me: Optional[float] = None
    blueprint_te: Optional[float] = None
    facility_key: str = "amamake"
    build_fuel_blocks: bool = False
    # Intermediate product type ids to import instead of manufacturing/reacting.
    exclude_type_ids: Optional[List[int]] = None
    # Convert leaf BOM → compressed ore + freighter imports.
    compressed: bool = False
    # Manual refine yield override (fraction). Wins over character/facility.
    refine_rate: Optional[float] = None
    # Eve character_id whose stored skills drive refine rate (when compressed).
    # Omit for max skills (V). Implant is controlled separately.
    character_id: Optional[int] = None
    # When true, apply RX implant bonus (character fitted, or RX-804 if max skills).
    use_reprocessing_implants: bool = False
    # ISK per LP for navy/faction BPC acquisition cost (omit to skip).
    isk_per_lp: Optional[float] = None
    # Optional EVE inventory / assets / Multibuy paste; subtracts from shopping list.
    stock_paste: Optional[str] = None
    # Cap each job at this many runs (blueprint copy limit). Omit for one job.
    # Materials and install cost are rounded per job, then summed.
    max_runs_per_job: Optional[int] = None
    # T2/T3 products only. "invent" (default) prices inventing the copy;
    # "supplied_bpc" builds from a copy you already have at bpc_me/bpc_te.
    # blueprint_me/te stay the BPOs for the rest of the tree.
    blueprint_source: Optional[str] = None
    # "auto" (cheapest per unit, default), "none", or a decryptor type id.
    decryptor: Optional[str] = None
    # Pick the T1 blueprint or relic grade to invent from (default cheapest).
    invention_source_type_id: Optional[int] = None
    bpc_me: Optional[float] = None
    bpc_te: Optional[float] = None
    invention_skills: Optional[PlanInventionSkillsSchema] = None


class PlanProductSchema(Schema):
    type_id: int
    name: str
    quantity: int


class PlanMaterialSchema(Schema):
    type_id: int
    name: str
    quantity: int


class PlanJobSchema(Schema):
    product_type_id: int
    product_name: str
    activity_id: int
    job_class: str
    bucket: str
    runs: int
    # How the runs are split across blueprint copies. One job when uncapped.
    job_count: int = 1
    runs_per_job: int = 0
    remainder_runs: int = 0
    facility: str
    blueprint_me: float
    blueprint_te: float
    me_total: float
    te_multiplier: float
    duration_seconds: float
    eiv: float
    job_cost_isk: int
    materials: List[PlanMaterialSchema]


class PlanLeafMaterialSchema(Schema):
    type_id: int
    name: str
    quantity: int
    # Unit price the planner buys at (Jita sell, else Forge guide). The
    # name predates that; it used to be the CCP average price.
    average_price: float = 0.0
    estimated_buy_isk: float = 0.0


class PlanStockAppliedSchema(Schema):
    type_id: int
    name: str
    needed: int
    owned: int
    used: int
    remaining: int


class PlanImportLineSchema(Schema):
    name: str
    quantity: int


class PlanCharacterSkillsSchema(Schema):
    character_id: int
    character_name: str
    reprocessing_level: int
    reprocessing_efficiency_level: int
    simple_ore_processing_level: int
    coherent_ore_processing_level: int
    ubiquitous_moon_ore_processing_level: int
    ore_processing_level: int
    implant_bonus: float
    implant_type_id: Optional[int] = None
    implant_name: Optional[str] = None
    use_reprocessing_implants: bool


class OreRefineYieldSchema(Schema):
    ore_name: str
    skill_id: int
    skill_name: str
    skill_level: int
    refine_rate: float


class RefineRateRequestSchema(Schema):
    facility_key: str = "amamake"
    character_id: Optional[int] = None
    use_reprocessing_implants: bool = False
    refine_rate: Optional[float] = None


class RefineRateResponseSchema(Schema):
    facility_key: str
    refine_rate: float
    refine_rate_source: str
    character_skills: Optional[PlanCharacterSkillsSchema] = None
    ore_yields: List[OreRefineYieldSchema] = []


class PlanCompressedOreSchema(Schema):
    refine_rate: float
    refine_rate_source: str
    reprocessing_tax: float
    materials_tsv: str
    import_lines: List[PlanImportLineSchema]
    # Minerals/materials currently satisfied via compressed ore (allowlist).
    compression_covered: List[str] = []
    belt_ore_compressed: Dict[str, int]
    moon_ore_compressed: Dict[str, int]
    ice_compressed: Dict[str, int] = {}
    mineral_imports: Dict[str, int]
    pi_other_imports: Dict[str, int] = {}
    ice_imports: Dict[str, int] = {}
    other_imports: Dict[str, int] = {}
    expected_minerals: Dict[str, int]
    expected_ice_products: Dict[str, int] = {}
    mineral_delta: Dict[str, int]
    character_skills: Optional[PlanCharacterSkillsSchema] = None
    ore_yields: List[OreRefineYieldSchema] = []


class PlanCostLineItemSchema(Schema):
    key: str
    label: str
    amount_isk: int


class PlanInventionInputSchema(Schema):
    type_id: int
    name: str
    quantity_per_attempt: int
    unit_price: float
    # Expected use (fractional) vs whole attempts to buy for.
    expected_quantity: float
    buy_quantity: int


class PlanInventionOptionSchema(Schema):
    source_type_id: int
    source_name: str
    source_kind: str
    decryptor_type_id: Optional[int] = None
    decryptor_name: str
    chance: float
    runs_per_copy: int
    copy_me: int
    copy_te: int
    invention_per_unit_isk: float
    # Invention plus the root build job, per unit; the ranking key.
    per_unit_isk: float


class PlanInventionSchema(PlanInventionOptionSchema):
    kind: str
    units: int
    runs_needed: int
    copies_needed: float
    expected_attempts: float
    buy_attempts: int
    attempts_p90: int
    attempt_isk: float
    invention_materials_isk: float
    invention_job_costs_isk: float
    invention_isk: float
    science_seconds: float
    inputs: List[PlanInventionInputSchema]
    alternatives: List[PlanInventionOptionSchema]


class PlannerInventionSourceSchema(Schema):
    type_id: int
    name: str
    kind: str  # "t1_blueprint" | "relic"
    base_chance: float
    runs: int


class PlannerDecryptorSchema(Schema):
    type_id: int
    name: str
    probability_multiplier: float
    runs_modifier: int
    me_modifier: int
    te_modifier: int


class PlannerInventionInfoSchema(Schema):
    type_id: int
    name: str
    kind: str  # "T2" | "T3"
    sources: List[PlannerInventionSourceSchema]
    decryptors: List[PlannerDecryptorSchema]


class PlanCostBreakdownSchema(Schema):
    materials_jita_sell_isk: int
    manufacturing_job_costs_isk: int
    reaction_job_costs_isk: int
    total_job_costs_isk: int
    facility_tax_isk: int
    scc_tax_isk: int
    reprocessing_tax_isk: int
    taxes_isk: int
    freight_isk: int = 0
    freight_volume_m3: float = 0.0
    freight_billable_m3: int = 0
    freight_route_id: Optional[int] = None
    freight_route_label: Optional[str] = None
    navy_bpc_isk: int = 0
    invention_isk: int = 0
    invention_materials_isk: int = 0
    invention_job_costs_isk: int = 0
    grand_total_isk: int
    per_unit_isk: float
    output_quantity: int
    line_items: List[PlanCostLineItemSchema]


class PlanNavyBpcSchema(Schema):
    offer_id: int
    corporation_id: int
    type_id: int
    lp_cost: int
    isk_cost: int
    quantity: int
    packs: int
    isk_per_lp: float
    total_isk: int


class PlanStepSavingSchema(Schema):
    """Build vs buy for one intermediate step, with its inputs bought."""

    type_id: int
    name: str
    # Units the parent jobs consume.
    quantity: int
    # Inputs at Jita sell + freight, plus install cost and taxes.
    build_isk: int
    # Jita sell + freight for ``quantity``; null when the step has no price.
    buy_isk: Optional[int] = None
    # buy_isk - build_isk: what building this step saves. Null without a price.
    saving_isk: Optional[int] = None


class PlanResponseSchema(Schema):
    product: PlanProductSchema
    blueprint_me: float
    blueprint_te: float
    # "bpo", "navy_bpc", "invent" or "supplied_bpc" for the root product.
    blueprint_source: str = "bpo"
    # Product-aware BPO defaults (percent) for the tree, so clients don't
    # repeat the navy rule: 10/20, or 0/0 for faction hulls.
    default_blueprint_me: float = 10.0
    default_blueprint_te: float = 20.0
    # ME/TE (percent) of the copy the root is built from, when it is one.
    root_blueprint_me: Optional[float] = None
    root_blueprint_te: Optional[float] = None
    root_runs_per_copy: Optional[int] = None
    facility: str
    system_id: int
    manufacturing_index: float
    reaction_index: float
    indices_from_esi: bool
    total_duration_seconds: float
    total_job_cost_isk: int
    bucket_durations: Dict[str, float]
    jobs: List[PlanJobSchema]
    leaf_materials: List[PlanLeafMaterialSchema]
    estimated_materials_buy_isk: float = 0.0
    materials_tsv: str = ""
    compressed_ore: Optional[PlanCompressedOreSchema] = None
    cost_breakdown: Optional[PlanCostBreakdownSchema] = None
    navy_bpc: Optional[PlanNavyBpcSchema] = None
    invention: Optional[PlanInventionSchema] = None
    stock_applied: List[PlanStockAppliedSchema] = []
    stock_unresolved: List[str] = []
    # Every intermediate the product can use, whether ticked or not.
    step_savings: List[PlanStepSavingSchema] = []
