from typing import List

from authentication import AuthBearer
from ninja import ModelSchema, Router, Schema

from .models import EveCorporation

router = Router(tags=["Eve Online"])


class CorporationResponse(ModelSchema):
    class Meta:
        model = EveCorporation
        fields = "__all__"


class CreateCorporationRequest(Schema):
    corporation_id: int


@router.get(
    "/corporations", response=List[CorporationResponse], auth=AuthBearer()
)
def get_corporations(request):  # pylint: disable=unused-argument
    return EveCorporation.objects.all()


@router.get(
    "/corporations/{corporation_id}",
    response=CorporationResponse,
    auth=AuthBearer(),
)
def get_corporation_by_id(
    request, corporation_id: int
):  # pylint: disable=unused-argument
    return EveCorporation.objects.get(corporation_id=corporation_id)


@router.post("/corporations", response=CorporationResponse, auth=AuthBearer())
def create_corporation(
    request, payload: CreateCorporationRequest
):  # pylint: disable=unused-argument
    return EveCorporation.objects.create(**payload.dict())
