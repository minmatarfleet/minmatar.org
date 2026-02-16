"""Helpers for updating EVE market item history from ESI region history."""

import logging
from datetime import datetime
from decimal import Decimal

from eveonline.client import EsiClient
from eveuniverse.models import EveType

from market.models import EveMarketItemHistory

logger = logging.getLogger(__name__)


def update_region_market_history_for_type(
    region_id: int, type_id: int
) -> tuple[int, int]:
    """
    Fetch region market history for one type from ESI and upsert EveMarketItemHistory.
    Returns (rows_updated_or_created, days_in_response).
    """
    if not EveType.objects.filter(id=type_id).exists():
        logger.debug("Skipping type_id=%s (no EveType)", type_id)
        return 0, 0

    client = EsiClient(None)
    response = client.get_region_market_history(region_id, type_id)
    if not response.success():
        logger.warning(
            "Failed to fetch region history region_id=%s type_id=%s: %s",
            region_id,
            type_id,
            response.response_code,
        )
        return 0, 0

    entries = response.results() or []
    updated = 0
    for entry in entries:
        date_str = entry.get("date")
        if not date_str:
            continue
        try:
            # ESI returns "YYYY-MM-DD"
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            logger.warning("Invalid date in history: %r", date_str)
            continue

        EveMarketItemHistory.objects.update_or_create(
            region_id=region_id,
            item_id=type_id,
            date=date,
            defaults={
                "average": Decimal(str(entry.get("average", 0))),
                "highest": Decimal(str(entry.get("highest", 0))),
                "lowest": Decimal(str(entry.get("lowest", 0))),
                "order_count": int(entry.get("order_count", 0)),
                "volume": int(entry.get("volume", 0)),
            },
        )
        updated += 1

    return updated, len(entries)
