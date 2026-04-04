from fittings.endpoints.eve_fittings.schemas import (
    FittingResponse,
    RefitResponse,
)
from fittings.models import EveFitting, EveFittingRefit


def make_refit_response(refit: EveFittingRefit) -> RefitResponse:
    return RefitResponse(
        id=refit.id,
        name=refit.name,
        eft_format=refit.eft_format,
        description=refit.description or "",
        created_at=refit.created_at,
        updated_at=refit.updated_at,
    )


def make_fitting_response(fitting: EveFitting) -> FittingResponse:
    refits = [make_refit_response(refit) for refit in fitting.refits.all()]
    return FittingResponse(
        id=fitting.id,
        name=fitting.name,
        ship_id=fitting.ship_id,
        description=fitting.description,
        created_at=fitting.created_at,
        updated_at=fitting.updated_at,
        eft_format=fitting.eft_format,
        minimum_pod=fitting.minimum_pod,
        recommended_pod=fitting.recommended_pod,
        latest_version=fitting.latest_version,
        tags=list(fitting.tags or []),
        refits=refits,
    )
