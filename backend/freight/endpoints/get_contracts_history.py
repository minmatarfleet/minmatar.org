"""GET /contracts/history – finished freight contracts."""

from typing import List

from ninja import Router

from freight.models import EveFreightContract
from freight.endpoints.schemas import FreightContractResponse
from freight.endpoints.get_contracts import _build_contract_response

router = Router(tags=["Freight"])


@router.get(
    "/history",
    description="Fetch finished (completed) freight contracts.",
    response=List[FreightContractResponse],
)
def get_contracts_history(request):
    qs = (
        EveFreightContract.objects.filter(status="finished")
        .select_related(
            "issuer",
            "issuer__user",
            "issuer__user__eveplayer",
            "issuer__user__eveplayer__primary_character",
            "completed_by",
            "completed_by__eveplayer",
            "completed_by__eveplayer__primary_character",
        )
        .prefetch_related("completed_by__evecharacter_set")
        .order_by("-date_completed")
    )
    return [_build_contract_response(c) for c in qs]
