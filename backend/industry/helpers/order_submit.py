"""Authorization helpers for creating industry manufacturing orders."""

from datetime import date, timedelta

from django.utils import timezone

from eveonline.helpers.characters import user_characters
from eveonline.models import EveCorporation, EveLocation
from groups.helpers.feature_access import can_use_feature
from industry.models import IndustryProduct
from industry.models.product import Strategy

ORDER_SUBMIT_FEATURE = "industry.order.submit"
ORDER_SUBMIT_PRODUCED_FEATURE = "industry.order.submit.produced"
MIN_ORDER_LEAD_DAYS = 14


def user_can_submit_orders_unrestricted(user) -> bool:
    """Tribe chiefs (and superusers) may create orders for any Eve type."""
    return can_use_feature(user, ORDER_SUBMIT_FEATURE)


def user_can_submit_produced_orders(user) -> bool:
    """Market members may create orders limited to produced catalog items."""
    return can_use_feature(user, ORDER_SUBMIT_PRODUCED_FEATURE)


def user_can_submit_orders(user) -> bool:
    return user_can_submit_orders_unrestricted(
        user
    ) or user_can_submit_produced_orders(user)


def user_must_submit_produced_only(user) -> bool:
    """True when the user may submit only produced catalog lines."""
    return user_can_submit_produced_orders(
        user
    ) and not user_can_submit_orders_unrestricted(user)


def order_submit_capabilities(user) -> dict[str, bool]:
    unrestricted = user_can_submit_orders_unrestricted(user)
    produced = user_can_submit_produced_orders(user)
    return {
        "can_submit": unrestricted or produced,
        "produced_only": produced and not unrestricted,
    }


def validate_produced_catalog_items(eve_type_ids: list[int]) -> list[int]:
    """
    Return type IDs that are not IndustryProduct with strategy=produced.

    Empty list means all IDs are valid produced catalog items.
    """
    if not eve_type_ids:
        return []
    produced_ids = set(
        IndustryProduct.objects.filter(
            eve_type_id__in=eve_type_ids,
            strategy=Strategy.PRODUCED,
        ).values_list("eve_type_id", flat=True)
    )
    return [tid for tid in eve_type_ids if tid not in produced_ids]


def earliest_needed_by_date(today: date | None = None) -> date:
    """Earliest allowed needed_by date (today + minimum lead time)."""
    base = today if today is not None else timezone.localdate()
    return base + timedelta(days=MIN_ORDER_LEAD_DAYS)


def validate_needed_by(needed_by: date) -> str | None:
    """
    Require needed_by at least MIN_ORDER_LEAD_DAYS from today.

    Returns an error detail string, or None when valid.
    """
    earliest = earliest_needed_by_date()
    if needed_by < earliest:
        return (
            f"Needed by must be at least {MIN_ORDER_LEAD_DAYS} days from today "
            f"(earliest: {earliest.isoformat()})."
        )
    return None


def resolve_staging_location(location_id: int | None):
    """
    Require a staging EveLocation.

    Returns (location, None) on success, or (None, error_detail).
    """
    if location_id is None:
        return None, "Delivery location is required."
    location = EveLocation.objects.filter(pk=location_id).first()
    if not location:
        return None, f"Location {location_id} not found."
    if not location.staging_active:
        return None, "Delivery location must be the active staging location."
    return location, None


def user_owned_delivery_entity_names(user) -> set[str]:
    """Character and corporation names the user can contract deliveries to."""
    characters = list(user_characters(user))
    names = {
        (character.character_name or "").strip()
        for character in characters
        if (character.character_name or "").strip()
    }
    corp_ids = {
        character.corporation_id
        for character in characters
        if character.corporation_id is not None
    }
    if corp_ids:
        names.update(
            EveCorporation.objects.filter(corporation_id__in=corp_ids)
            .exclude(name="")
            .values_list("name", flat=True)
        )
    return names


def validate_owned_delivery_entity(user, contract_to: str) -> str | None:
    """
    Require contract_to to match an owned character or corporation name.

    Returns an error detail string, or None when valid.
    """
    name = (contract_to or "").strip()
    if not name:
        return "Delivery entity (contract_to) is required."
    owned = user_owned_delivery_entity_names(user)
    if name not in owned:
        return (
            "Delivery entity must be a character or corporation you own "
            f"(unknown: {name})."
        )
    return None
