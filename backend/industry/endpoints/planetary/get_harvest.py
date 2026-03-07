"""GET "" - harvest overview: P0 types with total extractor counts (alliance-scoped)."""

from typing import List

from django.db.models import F, Sum, Value
from django.db.models.functions import Coalesce

from eveonline.models import EveCharacterPlanetOutput
from eveuniverse.models import EveType

from industry.endpoints.planetary.schemas import HarvestOverviewItem
from industry.helpers.alliance import get_alliance_character_ids

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Harvest overview: P0 types with total extractors and daily quantity",
    "response": {200: List[HarvestOverviewItem]},
}


def get_harvest(request):
    alliance_cids = get_alliance_character_ids()
    qs = (
        EveCharacterPlanetOutput.objects.filter(
            output_type=EveCharacterPlanetOutput.OutputType.HARVESTED,
            planet__character__character_id__in=alliance_cids,
        )
        .values("eve_type_id")
        .annotate(
            total_extractors=Coalesce(
                Sum(Coalesce(F("extractor_count"), Value(0))), Value(0)
            ),
            total_daily_quantity=Sum("daily_quantity"),
        )
        .order_by("eve_type_id")
    )
    type_ids = [r["eve_type_id"] for r in qs]
    names = dict(
        EveType.objects.filter(id__in=type_ids).values_list("id", "name")
    )
    return [
        HarvestOverviewItem(
            type_id=r["eve_type_id"],
            name=names.get(r["eve_type_id"], ""),
            total_extractors=int(r["total_extractors"] or 0),
            total_daily_quantity=(
                float(r["total_daily_quantity"])
                if r["total_daily_quantity"] is not None
                else None
            ),
        )
        for r in qs
    ]
