"""GET /contracts/history – finished freight contracts."""

from typing import List

from ninja import Router

from authentication import AuthLenient
from freight.models import FreightContract
from freight.endpoints.schemas import FreightContractResponse
from freight.endpoints.get_contracts import prepare_contract_responses

router = Router(tags=["Freight"])


@router.get(
    "/history",
    auth=AuthLenient(),
    description="Fetch finished (completed) freight contracts.",
    response=List[FreightContractResponse],
)
def get_contracts_history(request):
    contracts = list(
        FreightContract.objects.visible_to(request.auth)
        .finished()
        .order_by("-date_completed")
    )
    return prepare_contract_responses(contracts)
