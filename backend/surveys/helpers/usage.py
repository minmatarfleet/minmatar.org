"""Detect which transactional services a member has actually used, so we only
ask them to rate tools they've touched. All lookups read cached DB tables and
are individually guarded — a detection miss just hides that row (never errors).

Broadly-visible surfaces (community pages, learning, fleets, fittings) are NOT
gated here: "interaction" with them is a page view, not a transaction, so they
are always shown by the caller.
"""

import logging

from django.db.models import Q

from buyback.models import BuybackContract
from eveonline.helpers.characters import user_characters
from freight.models import FreightContract
from industry.models import (
    IndustryLoyaltyPointAccount,
    IndustryOrder,
    IndustryOrderItemAssignment,
)
from srp.models import EveFleetShipReimbursement

logger = logging.getLogger(__name__)

# Services that are always shown regardless of detected usage.
ALWAYS_ON_SERVICES = {"community", "learning", "fleets", "fittings"}

# Services gated on real, detectable interaction.
GATED_SERVICES = {"freight", "buyback", "loyalty", "orders", "market", "srp"}


def _char_ids(user) -> list[int]:
    try:
        return [c.character_id for c in user_characters(user)]
    except Exception:  # pragma: no cover - defensive
        return []


def _used_srp(user, char_ids) -> bool:
    try:
        return EveFleetShipReimbursement.objects.filter(user=user).exists()
    except Exception:  # pragma: no cover - defensive
        return False


def _used_freight(user, char_ids) -> bool:
    if not char_ids:
        return False
    try:
        return FreightContract.objects.filter(
            Q(issuer_id__in=char_ids) | Q(acceptor_id__in=char_ids)
        ).exists()
    except Exception:  # pragma: no cover - defensive
        return False


def _used_buyback(user, char_ids) -> bool:
    if not char_ids:
        return False
    try:
        return BuybackContract.objects.filter(issuer_id__in=char_ids).exists()
    except Exception:  # pragma: no cover - defensive
        return False


def _used_orders(user, char_ids) -> bool:
    if not char_ids:
        return False
    try:
        if IndustryOrder.objects.filter(character_id__in=char_ids).exists():
            return True
        return IndustryOrderItemAssignment.objects.filter(
            character_id__in=char_ids
        ).exists()
    except Exception:  # pragma: no cover - defensive
        return False


def _used_loyalty(user, char_ids) -> bool:
    try:
        return IndustryLoyaltyPointAccount.objects.filter(user=user).exists()
    except Exception:  # pragma: no cover - defensive
        return False


def _used_market(user, char_ids) -> bool:
    if not char_ids:
        return False
    try:
        # Import kept local: the referenced name is resolved defensively at
        # call time and a miss degrades to "not used" rather than erroring.
        from market.models import (  # pylint: disable=import-outside-toplevel
            AttributedOrder,
        )

        return AttributedOrder.objects.filter(
            owner_character_id__in=char_ids
        ).exists()
    except Exception:  # pragma: no cover - defensive
        return False


_DETECTORS = {
    "srp": _used_srp,
    "freight": _used_freight,
    "buyback": _used_buyback,
    "orders": _used_orders,
    "loyalty": _used_loyalty,
    "market": _used_market,
}


def member_service_usage(user) -> set[str]:
    """Return the set of GATED service keys this member has interacted with."""
    char_ids = _char_ids(user)
    used = set()
    for key, detector in _DETECTORS.items():
        try:
            if detector(user, char_ids):
                used.add(key)
        except Exception:  # pragma: no cover - defensive
            logger.debug("usage detector %s failed", key, exc_info=True)
    return used


def visible_service_keys(user) -> set[str]:
    """Always-on services + gated services the member has actually used."""
    return ALWAYS_ON_SERVICES | member_service_usage(user)
