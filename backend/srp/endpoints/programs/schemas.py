from pydantic import BaseModel


class ShipReimbursementProgramAmountResponse(BaseModel):
    id: int
    program_id: int
    srp_value: int
    created_at: str


class SetProgramAmountRequest(BaseModel):
    srp_value: int


class CreateProgramRequest(BaseModel):
    eve_type_id: int
    srp_value: int


class RecalculationChangeResponse(BaseModel):
    id: int
    ship_name: str
    character_name: str
    status: str
    current_amount: int
    new_amount: int
    character_id: int = 0
    created_at: str | None = None


class RecalculationPreviewResponse(BaseModel):
    outstanding_count: int
    changed_count: int
    current_total: int
    new_total: int
    changes: list[RecalculationChangeResponse]


class RecalculationResultResponse(BaseModel):
    updated: int
    errors: int


class ShipReimbursementProgramResponse(BaseModel):
    class EveCategoryResponse(BaseModel):
        id: int
        name: str

    class EveGroupResponse(BaseModel):
        id: int
        name: str

    class EveTypeResponse(BaseModel):
        id: int
        name: str

    id: int
    eve_type: EveTypeResponse
    eve_group: EveGroupResponse
    eve_category: EveCategoryResponse
    current_amount: ShipReimbursementProgramAmountResponse | None
    # Outstanding (pending/approved) requests for the hull, and those filed
    # at an amount it no longer pays (helpers.is_filed_at_old_amount).
    open_requests: int = 0
    stale_requests: int = 0
