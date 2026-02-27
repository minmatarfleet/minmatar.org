"""GET /contracts/history – finished freight contracts."""

from typing import List

from ninja import Router

from freight.models import FreightContract
from freight.endpoints.schemas import FreightContractResponse
from freight.endpoints.get_contracts import prepare_contract_responses

router = Router(tags=["Freight"])


@router.get(
    "/history",
    description="Fetch finished (completed) freight contracts.",
    response=List[FreightContractResponse],
)
def get_contracts_history(request):
    contracts = list(
        FreightContract.objects.finished().order_by("-date_completed")
    )
    return prepare_contract_responses(contracts)
