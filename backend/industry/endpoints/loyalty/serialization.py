"""Serialize LP buyback domain objects to API schemas."""

from dataclasses import dataclass, field

from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveCharacter, EvePlayer
from industry.endpoints.loyalty.schemas import (
    LoyaltyCurrencyResponse,
    LoyaltyLedgerEntryResponse,
    LoyaltyMarketOrderClaimResponse,
    LoyaltyMarketOrderResponse,
    LoyaltyOfferResponse,
)
from industry.helpers.lp_corporation_ids import corporation_ids
from industry.helpers.lp_market_orders import (
    claimed_quantity,
    express_due_at,
    remaining_quantity,
)
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLoyaltyPointLedgerEntry,
    IndustryLoyaltyPointMarketOrder,
    IndustryLoyaltyPointMarketOrderClaim,
    IndustryLpStoreOfferEconomics,
)


def _user_display_name(user) -> str:
    primary = user_primary_character(user)
    if primary:
        return primary.character_name
    return user.username


def currency_response(
    currency: IndustryLoyaltyPoint,
) -> LoyaltyCurrencyResponse:
    return LoyaltyCurrencyResponse(
        id=currency.pk,
        name=currency.name,
        corporation_id=int(currency.corporation_id),
        default_isk_per_lp=currency.default_isk_per_lp,
        express_isk_per_lp=currency.express_isk_per_lp,
        is_active=currency.is_active,
        allow_buy=currency.allow_buy,
        allow_sell=currency.allow_sell,
    )


@dataclass
class OrderContext:
    """Lookups shared by every order in a response, each done once.

    ``primaries`` maps user id -> primary character (or None), so names
    and portraits cost one query per response instead of four per pilot
    per order. ``corporation_ids`` maps lower-cased destination name ->
    corporation id for logos.
    """

    primaries: dict[int, EveCharacter | None] = field(default_factory=dict)
    corporation_ids: dict[str, int] = field(default_factory=dict)

    def name(self, user) -> str | None:
        if user is None:
            return None
        primary = self.primaries.get(user.pk)
        return primary.character_name if primary else user.username

    def character_id(self, user) -> int | None:
        if user is None:
            return None
        primary = self.primaries.get(user.pk)
        return int(primary.character_id) if primary else None

    def corporation_id(self, name: str) -> int | None:
        return self.corporation_ids.get((name or "").strip().lower())


def order_destination_names(
    order: IndustryLoyaltyPointMarketOrder,
) -> list[str]:
    """Corporation names an order's LP goes to (order and its claims)."""
    names = [order.destination_character_name]
    names += [c.destination_corporation_name for c in order.claims.all()]
    return [n for n in names if n]


def order_context(orders) -> OrderContext:
    """Batch the pilot and corporation lookups for ``orders``.

    Orders should come with ``claims__claimed_by`` prefetched.
    """
    user_ids: set[int] = set()
    names: list[str] = []
    for order in orders:
        user_ids.update(
            pk for pk in (order.created_by_id, order.claimed_by_id) if pk
        )
        user_ids.update(
            c.claimed_by_id for c in order.claims.all() if c.claimed_by_id
        )
        names += order_destination_names(order)
    primaries: dict[int, EveCharacter | None] = dict.fromkeys(user_ids)
    for player in EvePlayer.objects.filter(
        user_id__in=user_ids
    ).select_related("primary_character"):
        primaries[player.user_id] = player.primary_character
    return OrderContext(
        primaries=primaries, corporation_ids=corporation_ids(names)
    )


def market_order_claim_response(
    claim: IndustryLoyaltyPointMarketOrderClaim,
    context: OrderContext,
) -> LoyaltyMarketOrderClaimResponse:
    claimed_by = claim.claimed_by
    return LoyaltyMarketOrderClaimResponse(
        id=claim.pk,
        amount=int(claim.amount),
        destination_character_name=claim.destination_character_name or "",
        destination_corporation_name=claim.destination_corporation_name or "",
        destination_corporation_id=context.corporation_id(
            claim.destination_corporation_name
        ),
        claimed_by_user_id=claimed_by.pk if claimed_by else None,
        claimed_by_name=context.name(claimed_by),
        claimed_by_character_id=context.character_id(claimed_by),
        created_at=claim.created_at,
    )


def market_order_response(
    order: IndustryLoyaltyPointMarketOrder,
    context: OrderContext | None = None,
) -> LoyaltyMarketOrderResponse:
    """Serialize an order; pass ``order_context(orders)`` when listing."""
    if context is None:
        context = order_context([order])
    claimed_by = order.claimed_by
    created_by = order.created_by
    claims = [
        market_order_claim_response(claim, context)
        for claim in order.claims.all()
    ]
    return LoyaltyMarketOrderResponse(
        id=order.pk,
        loyalty_point_id=order.loyalty_point_id,
        loyalty_point_name=order.loyalty_point.name,
        corporation_id=int(order.loyalty_point.corporation_id),
        side=order.side,
        quantity=order.quantity,
        quantity_claimed=claimed_quantity(order),
        quantity_remaining=remaining_quantity(order),
        isk_per_lp=order.isk_per_lp,
        tier=order.tier,
        express_due_at=express_due_at(order),
        status=order.status,
        created_by_user_id=created_by.pk if created_by else None,
        created_by_name=context.name(created_by),
        created_by_character_id=context.character_id(created_by),
        claimed_by_user_id=claimed_by.pk if claimed_by else None,
        claimed_by_name=context.name(claimed_by),
        claimed_by_character_id=context.character_id(claimed_by),
        destination_character_name=order.destination_character_name or "",
        destination_corporation_id=context.corporation_id(
            order.destination_character_name
        ),
        discord_thread_id=order.discord_thread_id,
        notes=order.notes or "",
        claims=claims,
        created_at=order.created_at,
        updated_at=order.updated_at,
        completed_at=order.completed_at,
    )


def ledger_entry_response(
    entry: IndustryLoyaltyPointLedgerEntry,
) -> LoyaltyLedgerEntryResponse:
    account = entry.account
    created_by = entry.created_by
    return LoyaltyLedgerEntryResponse(
        id=entry.pk,
        account_id=account.pk,
        account_name=account.name,
        account_role=account.role,
        loyalty_point_id=account.loyalty_point_id,
        loyalty_point_name=account.loyalty_point.name,
        corporation_id=int(account.loyalty_point.corporation_id),
        amount=int(entry.amount),
        isk_per_lp=entry.isk_per_lp,
        balance_after=int(entry.balance_after),
        notes=entry.notes or "",
        market_order_id=entry.market_order_id,
        seller_user_id=entry.seller_user_id,
        seller_character_name=entry.seller_character_name or "",
        counterparty_user_id=entry.counterparty_user_id,
        counterparty_character_name=entry.counterparty_character_name or "",
        created_by_user_id=created_by.pk if created_by else None,
        created_by_name=(
            _user_display_name(created_by) if created_by else None
        ),
        created_at=entry.created_at,
    )


def offer_economics_row_response(
    row: IndustryLpStoreOfferEconomics,
) -> LoyaltyOfferResponse:
    return LoyaltyOfferResponse(
        offer_id=int(row.esi_offer_id),
        corporation_id=int(row.corporation_id),
        type_id=int(row.type_id),
        type_name=row.type_name,
        currency_name=row.currency_name or "",
        lp_cost=int(row.lp_cost),
        isk_cost=int(row.isk_cost),
        ak_cost=int(row.ak_cost),
        quantity=int(row.quantity),
        required_items_summary=row.required_items_summary or "",
        other_cost=row.other_cost,
        input_cost_isk=row.input_cost_isk,
        input_freight_isk=row.input_freight_isk,
        jita_sell=row.jita_sell,
        jita_buy=row.jita_buy,
        jita_avg_7d=row.jita_avg_7d,
        conversion_isk_per_lp_sell=row.conversion_isk_per_lp_sell,
        conversion_isk_per_lp_buy=row.conversion_isk_per_lp_buy,
        conversion_isk_per_lp_avg_7d=row.conversion_isk_per_lp_avg_7d,
        volume_1d=row.volume_1d,
        volume_7d=row.volume_7d,
        volume_30d=row.volume_30d,
        kind=row.kind or "",
        updated_at=row.offer_updated_at,
    )
