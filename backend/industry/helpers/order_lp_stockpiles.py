"""Resolve active LP stockpile accounts for navy/faction hulls on an order."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set

from django.db.models.functions import Lower
from eveonline.models import EveCorporation
from industry.helpers.blueprint_efficiency import is_faction_navy_hull
from industry.helpers.loyalty_store import get_offer_for_blueprint_type
from industry.helpers.lp_ledger import account_balance
from industry.helpers.type_breakdown import get_blueprint_or_reaction_type_id
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLoyaltyPointAccount,
    IndustryOrder,
)


@dataclass(frozen=True)
class OrderLpStockpileContact:
    character_name: str
    discord_user_id: Optional[int]
    discord_username: str


@dataclass(frozen=True)
class OrderLpStockpile:
    account_id: int
    account_name: str
    loyalty_point_id: int
    loyalty_point_name: str
    corporation_id: int
    balance: int
    contacts: List[OrderLpStockpileContact]
    character_id: Optional[int] = None
    account_corporation_id: Optional[int] = None


def corporation_ids_for_order_navy_blueprints(
    order: IndustryOrder,
) -> Set[int]:
    """
    Distinct LP-store corporation IDs for navy/faction hulls on the order.
    """
    corp_ids: Set[int] = set()
    items = order.items.select_related(
        "eve_type", "eve_type__eve_group", "eve_type__eve_group__eve_category"
    )
    for item in items:
        eve_type = item.eve_type
        if eve_type is None or not is_faction_navy_hull(eve_type):
            continue
        blueprint_type_id = get_blueprint_or_reaction_type_id(eve_type)
        if blueprint_type_id is None:
            continue
        offer = get_offer_for_blueprint_type(blueprint_type_id)
        if offer is None:
            continue
        corp_ids.add(int(offer.corporation_id))
    return corp_ids


def resolve_order_lp_stockpiles(
    order: IndustryOrder,
) -> List[OrderLpStockpile]:
    """
    Active stockpile accounts for LP currencies needed by this order's navy BPCs.
    """
    corp_ids = corporation_ids_for_order_navy_blueprints(order)
    if not corp_ids:
        return []

    currencies = list(
        IndustryLoyaltyPoint.objects.filter(
            corporation_id__in=corp_ids,
            is_active=True,
        )
    )
    if not currencies:
        return []

    currency_by_id = {c.pk: c for c in currencies}
    accounts = list(
        IndustryLoyaltyPointAccount.objects.filter(
            loyalty_point_id__in=currency_by_id.keys(),
            role=IndustryLoyaltyPointAccount.Role.STOCKPILE,
            is_active=True,
        )
        .select_related("loyalty_point", "eve_character")
        .prefetch_related("contacts")
        .order_by("loyalty_point__name", "name")
    )

    corp_ids_by_name = _corporation_ids_by_name(accounts)

    results: List[OrderLpStockpile] = []
    for account in accounts:
        currency = account.loyalty_point
        contacts = [
            OrderLpStockpileContact(
                character_name=c.character_name,
                discord_user_id=c.discord_user_id,
                discord_username=c.discord_username or "",
            )
            for c in account.contacts.all()
            if c.is_active
        ]
        character_id = _account_character_id(account)
        lookup_key = _holder_corp_lookup_key(account, character_id)
        account_corporation_id = (
            corp_ids_by_name.get(lookup_key) if lookup_key else None
        )
        results.append(
            OrderLpStockpile(
                account_id=account.pk,
                account_name=account.name,
                loyalty_point_id=currency.pk,
                loyalty_point_name=currency.name,
                corporation_id=int(currency.corporation_id),
                balance=account_balance(account),
                contacts=contacts,
                character_id=character_id,
                account_corporation_id=account_corporation_id,
            )
        )
    return results


def _account_character_id(
    account: IndustryLoyaltyPointAccount,
) -> Optional[int]:
    if account.eve_character_id and account.eve_character:
        return int(account.eve_character.character_id)
    return None


def _holder_corp_display_name(
    account: IndustryLoyaltyPointAccount,
    character_id: Optional[int],
) -> Optional[str]:
    """
    Name used to resolve a stockpile holder's corporation logo.

    Prefer explicit corporation_name. When that is blank and the account is not
    character-linked (e.g. Minmatar Fleet Holdings), fall back to account.name.
    """
    if account.corporation_name and account.corporation_name.strip():
        return account.corporation_name.strip()
    if character_id is None and account.name and account.name.strip():
        return account.name.strip()
    return None


def _holder_corp_lookup_key(
    account: IndustryLoyaltyPointAccount,
    character_id: Optional[int],
) -> Optional[str]:
    name = _holder_corp_display_name(account, character_id)
    return name.casefold() if name else None


def _corporation_ids_by_name(
    accounts: Sequence[IndustryLoyaltyPointAccount],
) -> Dict[str, int]:
    """Map casefolded Eve corp names → corporation_id for stockpile holders."""
    names: Set[str] = set()
    for account in accounts:
        name = _holder_corp_display_name(
            account, _account_character_id(account)
        )
        if name:
            names.add(name)
    if not names:
        return {}
    lower_names = {n.casefold() for n in names}
    return {
        (corp.name or "").strip().casefold(): int(corp.corporation_id)
        for corp in EveCorporation.objects.annotate(
            name_lower=Lower("name")
        ).filter(name_lower__in=lower_names)
        if corp.name
    }


def validate_coordinator_eve_type_ids(
    order: IndustryOrder,
    eve_type_ids: Sequence[int],
) -> Optional[str]:
    """
    Return an error detail if any type is missing from the order; else None.
    """
    if not eve_type_ids:
        return "Select at least one ship type from this order."
    order_type_ids = set(order.items.values_list("eve_type_id", flat=True))
    requested = {int(t) for t in eve_type_ids}
    invalid = requested - order_type_ids
    if invalid:
        return "These types are not on this order: " + ", ".join(
            str(t) for t in sorted(invalid)
        )
    return None
