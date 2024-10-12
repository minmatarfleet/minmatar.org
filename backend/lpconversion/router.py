from django.http import HttpResponse
from datetime import datetime
from pydantic import BaseModel
from ninja import Router
from typing import List

from authentication import AuthBearer
from app.errors import ErrorResponse

from .models import LpStoreItem, LpSellOrder, LpSellOrderPurchase, get_status
from .tasks import get_tlf_lp_items, update_lpstore_items

router = Router(tags=["conversion"])
active_rate = 645


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


@router.get("/status", response=str)
def conversion_status(request):
    get_tlf_lp_items()
    return get_status()


@router.get("/refresh", response=str)
def refresh_lpitem_data(request):
    update_lpstore_items.apply()
    return get_status()


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


class OfferResponse(BaseModel):
    offer_id: int
    user_id: int
    corporation: str
    loyalty_points: int
    rate: int
    created_at: datetime
    order: OrderResponse


@router.get(
    "/offers",
    response=List[OfferResponse],
    # auth=AuthBearer(),
)
def get_open_offers(request):
    offers = [
        OfferResponse(
            offer_id=123,
            user_id=987,
            corporation="AnyCorp",
            loyalty_points=2000000,
            rate=700,
            created_at=datetime.Now(),
            order=OrderResponse(
                order_id=12345,
                user_id=123,
                loyalty_points=2000000,
                rate=700,
                status="accepted",
                created_at=datetime.now(),
            ),
        )
    ]
    return offers


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
        seller=request.user.id,
        loyalty_points=order_details.loyalty_points,
        rate=active_rate,
    )

    return order.id


class CreateLpOfferRequest(BaseModel):
    corp_name: str


@router.post(
    "/orders/{order_id}/offers",
    response=int,
    auth=AuthBearer(),
)
def create_offer(request, order_id: int, order_details: CreateLpOfferRequest):
    if not request.user.has_perm("lpconversion.add_lpsellorder"):
        return ErrorResponse(
            detail="You do not have permission to create offers"
        )

    order = LpSellOrder.objects.get(order_id)
    order.status = "accepted"
    order.save()

    offer = LpSellOrderPurchase.objects.create(
        buyer=request.user.id,
        order=order,
        loyalty_points=order.loyalty_points,
        rate=order.rate,
        corporation=order_details.corporation,
    )

    return offer.id
