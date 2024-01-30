from typing import List

from ninja import ModelSchema, Router, Schema

from authentication import AuthBearer, requires_permission
from eveonline.models import EveCorporation, EveCorporationApplication

router = Router(tags=["Corporations"])


class CorporationResponse(ModelSchema):
    class Meta:
        model = EveCorporation
        fields = "__all__"


class CorporationApplicationResponse(Schema):
    status: str
    description: str
    corporation_id: int


class CreateCorporationRequest(Schema):
    corporation_id: int


@router.get(
    "/corporations",
    response=List[CorporationResponse],
    auth=AuthBearer(),
    summary="Get all corporations",
)
def get_corporations(request):
    return EveCorporation.objects.all()


@router.get(
    "/corporations/{corporation_id}",
    response=CorporationResponse,
    auth=AuthBearer(),
    summary="Get a corporation by ID",
)
def get_corporation_by_id(request, corporation_id: int):
    return EveCorporation.objects.get(corporation_id=corporation_id)


@router.post(
    "/corporations",
    response=CorporationResponse,
    auth=AuthBearer(),
    summary="Create a corporation",
)
@requires_permission("eveonline.add_evecorporation")
def create_corporation(request, payload: CreateCorporationRequest):
    return EveCorporation.objects.create(**payload.dict())


@router.get(
    "/corporations/applications",
    response=List[CorporationApplicationResponse],
    auth=AuthBearer(),
    summary="Get corporation applications",
)
@requires_permission("eveonline.view_evecorporationapplication")
def get_corporation_applications(request):
    return EveCorporationApplication.objects.all()
