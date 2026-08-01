"""GET /ledger - chronological LP account ledger transactions."""

from typing import List, Optional

from ninja import Query

from industry.endpoints.loyalty.schemas import LoyaltyLedgerEntryResponse
from industry.endpoints.loyalty.serialization import ledger_entry_response
from industry.models import IndustryLoyaltyPointLedgerEntry

PATH = "/ledger"
METHOD = "get"
DEFAULT_LIMIT = 100
MAX_LIMIT = 500

ROUTE_SPEC = {
    "summary": (
        "List loyalty-point ledger entries (credits/debits) newest first"
    ),
    "response": {200: List[LoyaltyLedgerEntryResponse]},
}


def get_ledger(
    request,
    loyalty_point_id: Optional[int] = Query(None),
    account_id: Optional[int] = Query(None),
    limit: Optional[int] = Query(None),
):
    qs = IndustryLoyaltyPointLedgerEntry.objects.select_related(
        "account",
        "account__loyalty_point",
        "created_by",
        "seller_user",
        "counterparty_user",
        "market_order",
    ).order_by("-created_at", "-id")
    if loyalty_point_id is not None:
        qs = qs.filter(account__loyalty_point_id=loyalty_point_id)
    if account_id is not None:
        qs = qs.filter(account_id=account_id)
    page_size = DEFAULT_LIMIT if limit is None else int(limit)
    page_size = max(1, min(page_size, MAX_LIMIT))
    return [ledger_entry_response(entry) for entry in qs[:page_size]]
