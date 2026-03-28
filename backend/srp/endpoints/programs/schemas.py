from pydantic import BaseModel


class ShipReimbursementProgramAmountResponse(BaseModel):
    id: int
    program_id: int
    srp_value: int
    created_at: str


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
