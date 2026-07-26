"""Helpers for whether market contracts count toward stock / expectations."""

from django.db.models import Q

# Shared with content matching (kept here to avoid model <-> match circular imports).
MATCH_THRESHOLD = 0.80


def outstanding_stock_q() -> Q:
    """
    Outstanding contracts that count toward stock.

    Pending name matches (items not fetched yet) still count. After items are
    fetched, only verified matches at or above MATCH_THRESHOLD count.
    """
    return Q(status="outstanding", fitting_id__isnull=False) & (
        Q(items_fetched=False) | Q(match_score__gte=MATCH_THRESHOLD)
    )
