"""GET /stock/stats – buyback stockpile overview metrics."""

from ninja import Router

from buyback.endpoints.schemas import BuybackStockStatsResponse
from buyback.helpers.stock_stats import compute_stock_stats

router = Router(tags=["Buyback"])


@router.get(
    "/stats",
    description=(
        "Buyback stockpile overview: Jita guide value of the stock "
        "listed for sale (same pool as /stock), value held for pending "
        "purchases, "
        "M-EXC corp wallet balance, and 30d stockpile turnover."
    ),
    response=BuybackStockStatsResponse,
)
def get_stock_stats(request):
    stats = compute_stock_stats()
    return BuybackStockStatsResponse(
        stockpile_value=stats["stockpile_value"],
        reserved_value=stats["reserved_value"],
        remaining_isk=stats["remaining_isk"],
        turnover_value=stats["turnover_value"],
        window_days=stats["window_days"],
    )
