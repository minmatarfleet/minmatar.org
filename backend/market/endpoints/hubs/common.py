"""Shared helpers for the market hub editor."""

from app.errors import ErrorResponse
from audit.helpers import record_change
from eveonline.models import EveLocation
from fittings.models import EveFitting
from groups.helpers.feature_access import can_use_feature
from market.endpoints.hubs.schemas import FittingExpectationRow, HubResponse
from market.models import (
    EveMarketContractExpectation,
    EveMarketFittingExpectation,
    EveMarketItemExpectation,
)

FEATURE = "market.manage"


def allowed(request) -> bool:
    return can_use_feature(request.user, FEATURE)


def forbidden():
    return 403, ErrorResponse.new("Market management permission required")


def hub_response(location: EveLocation) -> HubResponse:
    return HubResponse(
        location_id=location.location_id,
        location_name=location.location_name,
        short_name=location.short_name,
        solar_system_name=location.solar_system_name,
        market_active=location.market_active,
        prices_active=location.prices_active,
        price_baseline=location.price_baseline,
        fitting_expectations=EveMarketFittingExpectation.objects.filter(
            location=location
        ).count(),
        contract_expectations=EveMarketContractExpectation.objects.filter(
            location=location
        ).count(),
        item_expectations=EveMarketItemExpectation.objects.filter(
            location=location
        ).count(),
    )


def set_fitting_tracked(
    request, location_id, fitting_id, tracked, model, label
):
    if not allowed(request):
        return forbidden()
    location = EveLocation.objects.filter(location_id=location_id).first()
    fitting = EveFitting.objects.filter(pk=fitting_id).first()
    if location is None or fitting is None:
        return 404, ErrorResponse.new("Hub or fitting not found")
    if tracked:
        model.objects.update_or_create(
            location=location, fitting=fitting, defaults={"quantity": 1}
        )
    else:
        model.objects.filter(location=location, fitting=fitting).delete()
    record_change(
        request.user,
        f"{label} {'tracked' if tracked else 'untracked'}: "
        f"{fitting.name} at {location.location_name}",
    )
    return 200, FittingExpectationRow(
        fitting_id=fitting.pk, fitting_name=fitting.name, tracked=tracked
    )
