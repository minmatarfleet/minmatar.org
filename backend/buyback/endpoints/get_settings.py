"""GET /settings – public buyback program info."""

from ninja import Router

from buyback.endpoints.schemas import (
    BuybackAcceptedItemResponse,
    BuybackLocationResponse,
    BuybackRateRules,
    BuybackSettingsResponse,
    BuybackUsedInProduct,
)
from buyback.helpers.annotate import annotate_active_accepted_items
from buyback.helpers.pricing import public_rate_rules
from buyback.models import (
    BUYBACK_CORPORATION_ID,
    EveBuybackSettings,
)

router = Router(tags=["Buyback"])


@router.get(
    "/settings",
    description="Buyback program info: what we buy, rates, location.",
    response=BuybackSettingsResponse,
)
def get_settings(request):
    settings = EveBuybackSettings.load()
    location = None
    if settings.location_id:
        loc = settings.location
        location = BuybackLocationResponse(
            location_id=loc.location_id,
            name=loc.location_name,
            short_name=loc.short_name or loc.location_name,
        )

    active = bool(settings.active and location)
    rates = public_rate_rules(settings.rate_rules)

    return BuybackSettingsResponse(
        active=active,
        assignee_name=settings.assignee_name,
        corporation_id=BUYBACK_CORPORATION_ID,
        location=location,
        accepted_categories=settings.accepted_categories,
        accepted_items=[
            BuybackAcceptedItemResponse(
                type_id=item.type_id,
                name=item.name,
                category=item.category,
                used_in=[
                    BuybackUsedInProduct(
                        type_id=entry.type_id,
                        name=entry.name,
                    )
                    for entry in item.used_in
                ],
                in_demand=item.in_demand,
            )
            for item in annotate_active_accepted_items()
        ],
        rate_rules=BuybackRateRules(
            ore_refine=rates["ore_refine"],
            demand_jita_buy=rates["demand_jita_buy"],
            surplus_jita_buy=rates["surplus_jita_buy"],
        ),
        exclusions=settings.exclusions,
        discord_thread_url=settings.discord_thread_url,
        leading_text=settings.leading_text,
    )
