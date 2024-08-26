from ninja import Router

from .models import get_status

router = Router(tags=["conversion"])


@router.get("/routes", response=str)
def conversion_status(request):
    return get_status()
