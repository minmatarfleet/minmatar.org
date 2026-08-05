"""Serialize LP buyback domain objects to API schemas."""

from eveonline.helpers.characters import user_primary_character
from industry.endpoints.loyalty.schemas import (
    LoyaltyCurrencyResponse,
    LoyaltyLedgerEntryResponse,
    LoyaltyMarketOrderClaimResponse,
    LoyaltyMarketOrderResponse,
    LoyaltyOfferResponse,
)
from industry.helpers.lp_market_orders import (
    claimed_quantity,
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


def _user_character_id(user) -> int | None:
    primary = user_primary_character(user)
    if primary:
        return int(primary.character_id)
    return None


def currency_response(
    currency: IndustryLoyaltyPoint,
) -> LoyaltyCurrencyResponse:
    return LoyaltyCurrencyResponse(
        id=currency.pk,
        name=currency.name,
        corporation_id=int(currency.corporation_id),
        default_isk_per_lp=currency.default_isk_per_lp,
        is_active=currency.is_active,
    )


def market_order_claim_response(
    claim: IndustryLoyaltyPointMarketOrderClaim,
) -> LoyaltyMarketOrderClaimResponse:
    return LoyaltyMarketOrderClaimResponse(
        id=claim.pk,
        amount=int(claim.amount),
        destination_character_name=claim.destination_character_name or "",
        destination_corporation_name=claim.destination_corporation_name or "",
        claimed_by_user_id=claim.claimed_by_id,
        claimed_by_name=_user_display_name(claim.claimed_by),
        claimed_by_character_id=_user_character_id(claim.claimed_by),
        created_at=claim.created_at,
    )


def market_order_response(
    order: IndustryLoyaltyPointMarketOrder,
) -> LoyaltyMarketOrderResponse:
    claimed_by = order.claimed_by
    qty_claimed = claimed_quantity(order)
    claims = [
        market_order_claim_response(claim) for claim in order.claims.all()
    ]
    return LoyaltyMarketOrderResponse(
        id=order.pk,
        loyalty_point_id=order.loyalty_point_id,
        loyalty_point_name=order.loyalty_point.name,
        corporation_id=int(order.loyalty_point.corporation_id),
        side=order.side,
        quantity=order.quantity,
        quantity_claimed=qty_claimed,
        quantity_remaining=remaining_quantity(order),
        isk_per_lp=order.isk_per_lp,
        status=order.status,
        created_by_user_id=order.created_by_id,
        created_by_name=_user_display_name(order.created_by),
        created_by_character_id=_user_character_id(order.created_by),
        claimed_by_user_id=claimed_by.pk if claimed_by else None,
        claimed_by_name=(
            _user_display_name(claimed_by) if claimed_by else None
        ),
        claimed_by_character_id=(
            _user_character_id(claimed_by) if claimed_by else None
        ),
        destination_character_name=order.destination_character_name or "",
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
