from ninja import Router

from django.http import HttpResponse

from .models import LpStoreItem, get_status
from .tasks import update_lpstore_items

router = Router(tags=["conversion"])


@router.get("/lpitems/csv", response=str)
def item_data(request):
    response = HttpResponse(
        content_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="lp_items.csv"'},
    )
    response.write("type_id, item_name, qty_1d, qty_7d, qty_30d\n")
    for lp_item in LpStoreItem.objects.all():
        response.write(str(lp_item.type_id) + ", ")
        response.write(str(lp_item.description) + ", ")
        response.write(str(lp_item.qty_1d) + ", ")
        response.write(str(lp_item.qty_7d) + ", ")
        response.write(str(lp_item.qty_30d))
        response.write("\n")

    return response


@router.get("/status", response=str)
def conversion_status(request):
    return get_status()


@router.get("/refresh", response=str)
def refresh_lpitem_data(request):
    update_lpstore_items()
    return get_status()
