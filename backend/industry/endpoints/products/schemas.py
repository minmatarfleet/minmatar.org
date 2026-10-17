"""Schemas for industry products endpoints."""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel


class IndustryProductRef(BaseModel):
    """Minimal product reference for relations (supplied_for, supplies)."""

    id: int
    type_id: int
    name: str


class CharacterProducerRef(BaseModel):
    """Character producing this product type (industry jobs, planetary, and/or mining; total_value_isk aggregated)."""

    id: int
    name: str
    total_value_isk: float = 0.0


class CorporationProducerRef(BaseModel):
    """Corporation with industry jobs producing this product type (Eve corporation_id, name)."""

    id: int
    name: str
    total_value_isk: float = 0.0


class IndustryProductListItem(BaseModel):
    """One industry product in list: type, strategy, volume, blueprint/reaction, relations.

    Producers are omitted from the list payload; fetch via GET /products/{id}.
    """

    id: int
    type_id: int
    name: str
    strategy: str
    volume: Optional[float] = None
    blueprint_or_reaction_type_id: Optional[int] = None
    supplied_for: List[IndustryProductRef] = []
    supplies: List[IndustryProductRef] = []


class IndustryProductDetail(BaseModel):
    """Full industry product detail: all fields plus supplied_for, supplies, producers."""

    id: int
    type_id: int
    name: str
    strategy: str
    volume: Optional[float] = None
    blueprint_or_reaction_type_id: Optional[int] = None
    supplied_for: List[IndustryProductRef] = []
    supplies: List[IndustryProductRef] = []
    character_producers: List[CharacterProducerRef] = []
    corporation_producers: List[CorporationProducerRef] = []


class ProductBuilder(BaseModel):
    """A pilot (collapsed to their main) who finished builds in the window."""

    character_id: int
    character_name: str
    units: int
    jobs: int
    last_built_at: Optional[datetime] = None


class ProductBuilderCorporation(BaseModel):
    corporation_id: int
    corporation_name: str
    units: int


class ProductBuilt(BaseModel):
    units_30d: int = 0
    units_90d: int = 0
    jobs_90d: int = 0
    builders_90d: int = 0
    running_units: int = 0
    running_jobs: int = 0
    last_built_at: Optional[datetime] = None


class ProductOrderLine(BaseModel):
    order_id: int
    public_short_code: Optional[str] = None
    character_id: Optional[int] = None
    character_name: str = ""
    created_at: datetime
    needed_by: Optional[date] = None
    fulfilled_at: Optional[datetime] = None
    quantity: int
    assigned: int = 0
    delivered: int = 0


class ProductOrders(BaseModel):
    open_orders: int = 0
    open_units: int = 0
    open_assigned_units: int = 0
    open_delivered_units: int = 0
    ordered_units_90d: int = 0
    recent: List[ProductOrderLine] = []


class ProductLocationCount(BaseModel):
    location_name: str
    units: int


class ProductSales(BaseModel):
    market_units_30d: int = 0
    market_units_90d: int = 0
    contract_units_30d: int = 0
    contract_units_90d: int = 0
    listed_units: int = 0
    lowest_listed_price: Optional[float] = None
    outstanding_contracts: int = 0
    locations: List[ProductLocationCount] = []


class ProductHangars(BaseModel):
    units: int = 0
    pilots: int = 0
    locations: List[ProductLocationCount] = []


class ProductLoss(BaseModel):
    killmail_id: int
    killmail_time: datetime
    character_id: Optional[int] = None
    character_name: str = ""
    solar_system_id: Optional[int] = None


class ProductFight(BaseModel):
    """Losses in one system close together in time (see FIGHT_GAP)."""

    solar_system_id: int
    solar_system_name: str = ""
    started_at: datetime
    ended_at: datetime
    units: int
    killmail_id: int


class ProductLosses(BaseModel):
    units_30d: int = 0
    units_90d: int = 0
    recent: List[ProductLoss] = []
    # Biggest fights in the window; the rest are summed below.
    fights: List[ProductFight] = []
    small_fight_units: int = 0
    small_fight_systems: int = 0


class ProductRunningJob(BaseModel):
    character_id: int
    character_name: str = ""
    corporation_name: str = ""
    units: int
    ends_at: datetime


class ProductWeek(BaseModel):
    week_start: datetime
    built: int = 0
    sold: int = 0
    lost: int = 0


class ProductInsights(BaseModel):
    """Cached supply chain insights. ``ready`` is false while they compute."""

    ready: bool
    generated_at: Optional[datetime] = None
    is_ship: bool = False
    window_days: int = 90
    recent_days: int = 30
    unit_price: Optional[float] = None
    built: ProductBuilt = ProductBuilt()
    builders: List[ProductBuilder] = []
    corporations: List[ProductBuilderCorporation] = []
    running: List[ProductRunningJob] = []
    orders: ProductOrders = ProductOrders()
    sales: ProductSales = ProductSales()
    # None when we don't track it (only ships are synced from hangars and
    # matched to killmails).
    hangars: Optional[ProductHangars] = None
    losses: Optional[ProductLosses] = None
    weekly: List[ProductWeek] = []


class ProductBuildMaterial(BaseModel):
    type_id: int
    name: str
    quantity: int  # per run, before material efficiency
    unit_price: Optional[float] = None
    line_cost: Optional[float] = None
    # Our sourcing strategy when the material is a tracked product.
    strategy: Optional[str] = None
    industry_product_id: Optional[int] = None


class ProductBuild(BaseModel):
    """One run of the product's blueprint or reaction at average prices.

    Base SDE quantities and time: no ME/TE, facility bonuses or job cost.
    The planner covers those.
    """

    product_id: int
    type_id: int
    blueprint_type_id: int
    activity: str
    products_per_run: int = 1
    time_seconds: int = 0
    sell_price: Optional[float] = None
    material_cost: Optional[float] = None
    # Run value minus materials; None unless every material has a price.
    margin: Optional[float] = None
    prices_complete: bool = False
    materials: List[ProductBuildMaterial] = []
