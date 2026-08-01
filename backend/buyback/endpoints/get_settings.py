"""GET /settings – public buyback program info."""

from ninja import Router

from buyback.endpoints.schemas import (
    BuybackAcceptedItemResponse,
    BuybackLocationResponse,
    BuybackRateRules,
    BuybackSettingsResponse,
)
from buyback.models import (
    BUYBACK_CORPORATION_ID,
    BuybackAcceptedItem,
    EveBuybackSettings,
)

router = Router(tags=["Buyback"])


def _parse_rate_rules(raw) -> BuybackRateRules:
    if not isinstance(raw, dict):
        return BuybackRateRules()
    return BuybackRateRules(
        ore_refine=raw.get("ore_refine", 0.85),
        ore_jita_buy=raw.get("ore_jita_buy", 1.0),
        p1_jita_buy_cap=raw.get("p1_jita_buy_cap", 0.9),
        other_jita_buy=raw.get("other_jita_buy", 1.0),
    )


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

    accepted_items = [
        BuybackAcceptedItemResponse(
            type_id=item.eve_type_id,
            name=item.eve_type.name,
            category=item.category,
        )
        for item in BuybackAcceptedItem.objects.filter(active=True)
        .select_related("eve_type")
        .order_by("category", "eve_type__name")
    ]

    return BuybackSettingsResponse(
        active=active,
        assignee_name=settings.assignee_name,
        corporation_id=BUYBACK_CORPORATION_ID,
        location=location,
        accepted_categories=settings.accepted_categories,
        accepted_items=accepted_items,
        rate_rules=_parse_rate_rules(settings.rate_rules),
        exclusions=settings.exclusions,
        discord_thread_url=settings.discord_thread_url,
        leading_text=settings.leading_text,
    )
