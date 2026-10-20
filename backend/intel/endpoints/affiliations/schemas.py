from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from ninja import Schema


class EntityRef(Schema):
    kind: str
    id: int
    name: str


class BlocRef(Schema):
    id: int
    name: str
    likely: bool = False


class AffiliationSchema(Schema):
    id: int
    entity: EntityRef
    bloc: BlocRef
    relation: str
    status: str
    source: str
    confidence: float
    evidence: dict
    first_month: date | None
    last_month: date | None
    ended: bool
    decided_by: str | None
    decided_at: datetime | None
    note: str


class QueueEntrySchema(EntityRef):
    sightings: int
    priority: int


class QueueStatsSchema(Schema):
    queued: int
    investigating: int
    investigated: int
    failed: int
    next: list[QueueEntrySchema]


class ReviewResponse(Schema):
    suggestions: list[AffiliationSchema]
    queue: QueueStatsSchema


class BlocSummarySchema(Schema):
    id: int
    name: str
    anchor: EntityRef | None
    notes: str
    manual: bool
    groups: int
    associates: int
    suggested: int


class BlocListResponse(Schema):
    blocs: list[BlocSummarySchema]


class BlocDetailResponse(BlocSummarySchema):
    affiliations: list[AffiliationSchema]


class PartnerSchema(EntityRef):
    shared: int
    share: float | None
    months_together: int
    against: int
    militia_shared: int
    last_month: date | None
    bloc: BlocRef | None


class EntityProfileResponse(EntityRef):
    status: str
    sightings: int
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    investigated_at: datetime | None
    faction_id: int | None
    kills_sampled: int
    losses_sampled: int
    months_sampled: int
    bloc: BlocRef | None
    alliance_history: list[dict]
    # Groups: who flies with them. Characters: whose kills they are on.
    partners: list[PartnerSchema]
    # Groups only: characters outside the group on its kills.
    characters: list[PartnerSchema]
    affiliations: list[AffiliationSchema]


class EntitySearchResult(EntityRef):
    status: str
    bloc: BlocRef | None


class EntitySearchListResponse(Schema):
    results: list[EntitySearchResult]


class DecisionRequest(Schema):
    status: Literal["confirmed", "rejected"]
    relation: Literal["pet", "alt", "ally", "associate", "member"] | None = (
        None
    )
    bloc_id: int | None = None
    note: str = ""


class ManualAffiliationRequest(Schema):
    kind: Literal["alliance", "corporation", "character"]
    eve_id: int | None = None
    name: str | None = None
    bloc_id: int | None = None
    new_bloc_name: str | None = None
    relation: Literal["pet", "alt", "ally", "associate", "member"]
    note: str = ""


class BlocPatchRequest(Schema):
    name: str | None = None
    notes: str | None = None


class BlocMergeRequest(Schema):
    into_bloc_id: int


class InvestigateResponse(EntityRef):
    status: str
    priority: int


class MemberCrosscheckRow(Schema):
    character_id: int
    character_name: str
    main_character_name: str | None
    bloc: BlocRef
    shared: int
    months_together: int
    last_month: date | None
    groups: list[EntityRef]


class MemberCrosscheckResponse(Schema):
    members: list[MemberCrosscheckRow]
