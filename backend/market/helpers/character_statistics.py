"""Build Market Ops character leaderboard (total ISK on market)."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Optional

from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce
from pydantic import BaseModel

from eveonline.models import EveCharacter, EveLocation, EvePlayer
from market.helpers.market_operators import eligible_market_operator_user_ids
from market.models import EveMarketAttributedOrder, EveMarketContract


class MarketCharacterStatResponse(BaseModel):
    primary_character_id: Optional[int] = None
    primary_character_name: Optional[str] = None
    total_isk_on_market: float


def build_market_character_statistics() -> list[MarketCharacterStatResponse]:
    """Rank eligible users by contract + sell ISK at market-active locations."""
    eligible_user_ids = eligible_market_operator_user_ids()
    if not eligible_user_ids:
        return []

    characters = EveCharacter.objects.filter(
        user_id__in=eligible_user_ids
    ).only("character_id", "user_id")
    char_to_user = {c.character_id: c.user_id for c in characters}
    char_ids = list(char_to_user.keys())
    if not char_ids:
        return []

    market_location_ids = list(
        EveLocation.objects.filter(market_active=True).values_list(
            "location_id", flat=True
        )
    )
    if not market_location_ids:
        return []

    user_totals: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    isk_field = DecimalField(max_digits=32, decimal_places=2)

    for row in (
        EveMarketAttributedOrder.objects.filter(
            owner_character_id__in=char_ids,
            is_buy_order=False,
            location_esi_id__in=market_location_ids,
        )
        .values("owner_character_id")
        .annotate(
            total=Coalesce(
                Sum(F("price") * F("volume_remain")),
                Value(0, output_field=isk_field),
            )
        )
    ):
        user_id = char_to_user.get(row["owner_character_id"])
        if user_id is not None:
            user_totals[user_id] += Decimal(row["total"] or 0)

    for row in (
        EveMarketContract.objects.filter(
            status="outstanding",
            issuer_external_id__in=char_ids,
            location_id__in=market_location_ids,
        )
        .values("issuer_external_id")
        .annotate(
            total=Coalesce(
                Sum("price"),
                Value(0, output_field=isk_field),
            )
        )
    ):
        user_id = char_to_user.get(row["issuer_external_id"])
        if user_id is not None:
            user_totals[user_id] += Decimal(row["total"] or 0)

    if not user_totals:
        return []

    primary_by_user = {}
    for player in (
        EvePlayer.objects.filter(user_id__in=user_totals.keys())
        .select_related("primary_character")
        .only(
            "user_id",
            "primary_character_id",
            "primary_character__character_id",
            "primary_character__character_name",
        )
    ):
        if player.primary_character_id:
            primary_by_user[player.user_id] = (
                player.primary_character.character_id,
                player.primary_character.character_name or "",
            )

    result: list[MarketCharacterStatResponse] = []
    for user_id, total in user_totals.items():
        total_float = float(total)
        if total_float <= 0:
            continue
        primary = primary_by_user.get(user_id)
        char_id, char_name = primary if primary else (None, None)
        result.append(
            MarketCharacterStatResponse(
                primary_character_id=char_id,
                primary_character_name=char_name or None,
                total_isk_on_market=round(total_float, 2),
            )
        )

    result.sort(
        key=lambda row: (
            -row.total_isk_on_market,
            (row.primary_character_name or "").lower(),
        )
    )
    return result
