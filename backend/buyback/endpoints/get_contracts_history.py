"""GET /contracts/history – finished buyback contracts."""

from typing import List

from ninja import Router

from buyback.endpoints.get_contracts import prepare_contract_responses
from buyback.endpoints.schemas import BuybackContractResponse
from buyback.models import BuybackContract

router = Router(tags=["Buyback"])


@router.get(
    "/history",
    description="Fetch finished (completed) buyback contracts.",
    response=List[BuybackContractResponse],
)
def get_contracts_history(request):
    contracts = list(
        BuybackContract.objects.finished().order_by("-date_completed")
    )
    return prepare_contract_responses(contracts)
