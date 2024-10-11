from django.http import HttpResponse
from ninja import Router

from .models import LpStoreItem, get_status
from .tasks import get_tlf_lp_items, update_lpstore_items

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


@router.get("/status", response=str)
def conversion_status(request):
    get_tlf_lp_items()
    return get_status()


@router.get("/refresh", response=str)
def refresh_lpitem_data(request):
    update_lpstore_items.apply()
    return get_status()
