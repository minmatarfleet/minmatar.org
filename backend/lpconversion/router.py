from django.http import HttpResponse
from datetime import datetime
from pydantic import BaseModel
from ninja import Router
from typing import List

from authentication import AuthBearer
from app.errors import ErrorResponse

from .models import (
    LpStoreItem,
    LpSellOrder,
    LpSellOrderPurchase,
    current_price,
)

# from .tasks import get_tlf_lp_items, update_lpstore_items

router = Router(tags=["conversion"])


@router.get("/lpitems/csv", response=str)
def item_data(request):
    response = HttpResponse(
        content_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="lp_items.csv"'},
    )
    response.write(
        "type_id, item_name, qty_1d, qty_7d, qty_30d, store_qty, store_lp, store_isk, sell_price, updated\n"
    )
    for lp_item in LpStoreItem.objects.all():
        response.write(str(lp_item.type_id) + ", ")
        response.write(str(lp_item.description) + ", ")
        response.write(str(lp_item.qty_1d) + ", ")
        response.write(str(lp_item.qty_7d) + ", ")
        response.write(str(lp_item.qty_30d) + ", ")
        response.write(str(lp_item.store_qty) + ", ")
        response.write(str(lp_item.store_lp) + ", ")
        response.write(str(lp_item.store_isk) + ", ")
        response.write(str(lp_item.jita_price) + ", ")
        response.write(str(lp_item.updated_at.strftime("%Y-%m-%dT%H:%M:%S")))
        response.write("\n")

    return response


# @router.get("/status", response=str)
# def conversion_status(request):
#     get_tlf_lp_items()
#     return get_status()


# @router.get("/refresh", response=str)
# def refresh_lpitem_data(request):
#     update_lpstore_items.apply()
#     return get_status()


class OrderResponse(BaseModel):
    order_id: int
    user_id: int
    loyalty_points: int
    rate: int
    status: str
    created_at: datetime


@router.get(
    "/orders",
    response=List[OrderResponse],
    auth=AuthBearer(),
)
def get_open_orders(request):
    response = []
    orders = LpSellOrder.objects.all()
    for order in orders:
        if order.status != "closed":
            response.append(
                OrderResponse(
                    order_id=order.id,
                    user_id=order.seller.id,
                    loyalty_points=order.loyalty_points,
                    rate=order.rate,
                    status=order.status,
                    created_at=order.created_at,
                )
            )
    return response


@router.get(
    "/orders/{order_id}",
    response=OrderResponse,
    auth=AuthBearer(),
)
def get_order(request, order_id):
    response = []
    order = LpSellOrder.objects.get(order_id)
    response = OrderResponse(
        order_id=order.id,
        user_id=order.seller.id,
        loyalty_points=order.loyalty_points,
        rate=order.rate,
        status=order.status,
        created_at=order.created_at,
    )

    return response


class PurchaseResponse(BaseModel):
    purchase_id: int
    user_id: int
    corporation: str
    loyalty_points: int
    rate: int
    created_at: datetime
    order: OrderResponse


class CreateLpOrderRequest(BaseModel):
    loyalty_points: int


@router.post(
    "/orders",
    response=int,
    auth=AuthBearer(),
)
def create_order(request, order_details: CreateLpOrderRequest):
    if not request.user.has_perm("lpconversion.add_lpsellorder"):
        return ErrorResponse(
            detail="You do not have permission to create orders"
        )

    order = LpSellOrder.objects.create(
        status="pending",
        seller_id=request.user.id,
        loyalty_points=order_details.loyalty_points,
        rate=current_price(),
    )

    return order.id


class CreateLpPurchaseRequest(BaseModel):
    corp_name: str


@router.post(
    "/orders/{order_id}/purchase",
    response=int,
    auth=AuthBearer(),
)
def create_purchase(
    request, order_id: int, order_details: CreateLpPurchaseRequest
):
    if not request.user.has_perm("lpconversion.add_lpsellorderpurchase"):
        return ErrorResponse(
            detail="You do not have permission to create purchases"
        )

    order = LpSellOrder.objects.get(order_id)
    order.status = "accepted"
    order.save()

    purchase = LpSellOrderPurchase.objects.create(
        buyer=request.user.id,
        order=order,
        loyalty_points=order.loyalty_points,
        rate=order.rate,
        corporation=order_details.corporation,
    )

    return purchase.id
