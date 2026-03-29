"""GET /metrics — aggregate fleet stats for analytics."""

from datetime import timedelta
from typing import List

from django.db.models import Count, F, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone

from authentication import AuthBearer
from eveonline.models import EveCorporation

from fleets.endpoints.helpers import time_region
from fleets.endpoints.schemas import EveFleetMetric
from fleets.models import EveFleet

PATH = "/metrics"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: List[EveFleetMetric]},
    "summary": "Get fleet metrics",
}


def get_fleet_metrics(request):
    metrics = []
    one_year_ago = timezone.now() - timedelta(days=365)
    fleets = (
        EveFleet.objects.filter(start_time__gte=one_year_ago)
        .annotate(instances=Count("evefleetinstance"))
        .annotate(members=Count("evefleetinstance__evefleetinstancemember"))
        .annotate(
            location_name=Coalesce(
                F("audience__staging_location__location_name"),
                F("location__location_name"),
            )
        )
        .annotate(
            fc_corporation_id=F(
                "created_by__eveplayer__primary_character__corporation_id"
            )
        )
        .annotate(
            fc_corp_name=Subquery(
                EveCorporation.objects.filter(
                    corporation_id=OuterRef(
                        "created_by__eveplayer__primary_character__corporation_id"
                    )
                ).values("name")[:1]
            )
        )
        .annotate(audience_name=F("audience__name"))
    )
    for fleet in fleets:
        fc_corp_name = fleet.fc_corp_name if fleet.fc_corp_name else ""
        corp_id = fleet.fc_corporation_id
        corp_id_out = int(corp_id) if corp_id is not None else None
        corp_name_out = fc_corp_name if fc_corp_name else None
        metric = EveFleetMetric(
            fleet_id=fleet.id,
            members=fleet.members,
            time_region=time_region(fleet.start_time),
            location_name=fleet.location_name if fleet.location_name else "",
            status=fleet.status,
            fc_corp_name=fc_corp_name,
            corporation_id=corp_id_out,
            corporation_name=corp_name_out,
            audience_name=fleet.audience_name if fleet.audience_name else "",
        )
        metrics.append(metric)
    return 200, metrics
