"""GET /delivery-locations - where a new order can deliver."""

from typing import List

from authentication import AuthBearer
from industry.endpoints.orders.schemas import OrderLocationResponse
from industry.helpers.delivery_location import order_location_fields
from industry.helpers.order_submit import delivery_locations

PATH = "/delivery-locations"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Locations a manufacturing order can deliver to",
    "auth": AuthBearer(),
    "response": {200: List[OrderLocationResponse]},
}


def get_order_delivery_locations(request):
    return [
        OrderLocationResponse(**order_location_fields(location))
        for location in delivery_locations()
    ]
