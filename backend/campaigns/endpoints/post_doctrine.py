"""One endpoint: see the function below."""

from __future__ import annotations

from django.db import transaction

from app.errors import ErrorResponse
from authentication import AuthBearer
from campaigns.endpoints import schemas
from campaigns.endpoints.base import router
from campaigns.endpoints.coordinator_helpers import _doctrines_out, _managed
from campaigns.models import CampaignDoctrine, CampaignFitting
from fittings.models import (
    DOCTRINE_FITTING_ROLE_LABELS,
    EveDoctrine,
    EveDoctrineFitting,
)


@router.post(
    "/{slug}/doctrines",
    response={
        200: schemas.CampaignDoctrinesOut,
        400: ErrorResponse,
        403: ErrorResponse,
        404: None,
    },
    auth=AuthBearer(),
)
def attach_doctrine(
    request, slug: str, payload: schemas.CampaignDoctrineAttach
):
    """Attach a doctrine; its fittings join the campaign, switched on."""
    campaign, denied = _managed(request, slug)
    if denied:
        return denied
    doctrine = EveDoctrine.objects.filter(id=payload.doctrine_id).first()
    if doctrine is None:
        return 400, {"detail": "No such doctrine."}
    with transaction.atomic():
        attached, created = CampaignDoctrine.objects.get_or_create(
            campaign=campaign, doctrine=doctrine
        )
        if created:
            already = set(
                campaign.fittings.values_list("fitting_id", flat=True)
            )
            order = campaign.fittings.count()
            for row in EveDoctrineFitting.objects.filter(
                doctrine=doctrine
            ).order_by("role", "id"):
                if row.fitting_id in already:
                    continue
                already.add(row.fitting_id)
                CampaignFitting.objects.create(
                    campaign=campaign,
                    fitting_id=row.fitting_id,
                    role_label=DOCTRINE_FITTING_ROLE_LABELS.get(
                        row.role, row.role.title()
                    ),
                    doctrine=attached,
                    order=order,
                )
                order += 1
    return _doctrines_out(campaign)
