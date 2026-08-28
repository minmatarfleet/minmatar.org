"""Serialize buyback purchase orders to API schemas."""

from buyback.endpoints.schemas import (
    BuybackPurchaseFillResponse,
    BuybackPurchaseOrderLineResponse,
    BuybackPurchaseOrderResponse,
    BuybackPurchasePick,
    BuybackPurchaseShortfall,
)
from buyback.helpers.purchase_orders import serialize_fill, serialize_order
from buyback.models import BuybackPurchaseOrder


def fill_response(fill) -> BuybackPurchaseFillResponse:
    data = serialize_fill(fill)
    return BuybackPurchaseFillResponse(
        picks=[BuybackPurchasePick(**row) for row in data["picks"]],
        shortfalls=[
            BuybackPurchaseShortfall(**row) for row in data["shortfalls"]
        ],
        unresolved_names=data["unresolved_names"],
        janice_tsv=data["janice_tsv"],
        shortfall_tsv=data["shortfall_tsv"],
        contract_total=data["contract_total"],
        refine_rate=data["refine_rate"],
        refine_rate_source=data["refine_rate_source"],
        facility_key=data["facility_key"],
        facility_name=data["facility_name"],
        sell_price_basis=data["sell_price_basis"],
        sell_markup=data["sell_markup"],
    )


def order_response(
    order: BuybackPurchaseOrder,
) -> BuybackPurchaseOrderResponse:
    data = serialize_order(order)
    return BuybackPurchaseOrderResponse(
        id=data["id"],
        status=data["status"],
        source=data["source"],
        created_by_user_id=data["created_by_user_id"],
        character_id=data["character_id"],
        character_name=data["character_name"],
        contract_total=data["contract_total"],
        sell_price_basis=data["sell_price_basis"],
        sell_markup=data["sell_markup"],
        janice_tsv=data["janice_tsv"],
        created_at=data["created_at"],
        completed_at=data["completed_at"],
        discord_thread_id=data["discord_thread_id"],
        discord_thread_url=data["discord_thread_url"],
        lines=[
            BuybackPurchaseOrderLineResponse(**line) for line in data["lines"]
        ],
    )
