from ninja import Router, Schema, ModelSchema
from auth import AuthBearer
from typing import List
from .models import EveCorporation

router = Router()


class CorporationResponse(ModelSchema):
    class Meta:
        model = EveCorporation
        fields = "__all__"


class CreateCorporationRequest(Schema):
    corporation_id: int


@router.get("/corporations", response=List[CorporationResponse], auth=AuthBearer())
def get_corporations(request):
    return EveCorporation.objects.all()


@router.get("/corporations/{corporation_id}", response=CorporationResponse, auth=AuthBearer())
def get_corporation_by_id(request, corporation_id: int):
    return EveCorporation.objects.get(corporation_id=corporation_id)


@router.post("/corporations", response=CorporationResponse, auth=AuthBearer())
def create_corporation(request, payload: CreateCorporationRequest):
    return EveCorporation.objects.create(**payload.dict())
