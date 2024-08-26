from ninja import Router

from django.http import HttpResponse

from .models import get_status, get_item_data
from .tasks import update_lpstore_items

router = Router(tags=["conversion"])


@router.get("/", response=str)
def item_data(request):
    response = HttpResponse(
        content_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="lp_items.csv"'},
    )
    response.write(get_item_data())
    return response


@router.get("/status", response=str)
def conversion_status(request):
    return get_status()


@router.get("/refresh", response=str)
def refresh_lpitem_data(request):
    update_lpstore_items()
    return get_status()
