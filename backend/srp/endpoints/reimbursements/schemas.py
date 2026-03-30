"""Deprecated: use ``srp.endpoints.requests.schemas``."""

from srp.endpoints.requests.schemas import (
    CreateSrpRequest as CreateEveFleetReimbursementRequest,
    SrpCategory,
    SrpPatchResult,
    SrpRequestResponse as EveFleetReimbursementResponse,
    UpdateSrpRequest as UpdateEveFleetReimbursementRequest,
)

__all__ = [
    "CreateEveFleetReimbursementRequest",
    "EveFleetReimbursementResponse",
    "SrpCategory",
    "SrpPatchResult",
    "UpdateEveFleetReimbursementRequest",
]
