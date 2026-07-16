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
    average_price: float = 0.0
    estimated_buy_isk: float = 0.0


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
    mineral_imports: Dict[str, int]
    pi_other_imports: Dict[str, int] = {}
    ice_imports: Dict[str, int] = {}
    other_imports: Dict[str, int] = {}
    expected_minerals: Dict[str, int]
    mineral_delta: Dict[str, int]
    character_skills: Optional[PlanCharacterSkillsSchema] = None
    ore_yields: List[OreRefineYieldSchema] = []


class PlanCostLineItemSchema(Schema):
    key: str
    label: str
    amount_isk: int


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
    grand_total_isk: int
    per_unit_isk: float
    output_quantity: int
    line_items: List[PlanCostLineItemSchema]


class PlanResponseSchema(Schema):
    product: PlanProductSchema
    blueprint_me: float
    blueprint_te: float
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
