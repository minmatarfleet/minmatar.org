import logging
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from eveuniverse.models import EveType

from app.celery import app
from market.helpers.pricing import (
    enqueue_history_for_types,
    get_history_averages_by_type_id,
)
from moons.helpers import calc_metanox_yield
from moons.models import EveMoon, EveMoonDistribution, ore_yield_map

logger = logging.getLogger(__name__)

# Refresh a moon product's Forge history when its latest day is older.
HISTORY_MAX_AGE_DAYS = 2


def get_prices() -> dict[str, Decimal]:
    """
    Jita guide price per moon product name: the latest daily average from
    stored Forge (price_baseline region) history, then CCP's average price.

    Products without any price are left out. Products whose history is
    missing or stale get a history fetch queued for the next run.
    """
    names = sorted(
        {product for yields in ore_yield_map.values() for product in yields}
    )
    name_to_id = dict(
        EveType.objects.filter(name__in=names).values_list("name", "id")
    )
    unknown = [name for name in names if name not in name_to_id]
    if unknown:
        logger.warning("Moon products not in the universe cache: %s", unknown)

    stale_before = timezone.now().date() - timedelta(days=HISTORY_MAX_AGE_DAYS)
    enqueue_history_for_types(name_to_id.values(), stale_before=stale_before)

    by_id = get_history_averages_by_type_id(list(name_to_id.values()))
    prices = {
        name: by_id[type_id]
        for name, type_id in name_to_id.items()
        if type_id in by_id
    }
    unpriced = [name for name in name_to_id if name not in prices]
    if unpriced:
        logger.warning("Moon products with no market price: %s", unpriced)
    return prices


def calculate_moon_revenue(moon, distributions, prices) -> Decimal | None:
    """
    Monthly Metenox revenue for one moon, or None when a product it yields
    has no price (an estimate missing a product would be too low).
    """
    yields = calc_metanox_yield(distributions)
    missing = [product for product in yields if product not in prices]
    if missing:
        logger.warning(
            "%s %s %s: no price for %s; revenue not updated",
            moon.system,
            moon.planet,
            moon.moon,
            missing,
        )
        return None
    moon_revenue = Decimal(0.0)
    for moon_yield in yields:
        cycle_revenue = yields[moon_yield] * prices[moon_yield]
        logger.info(
            "%s %s %s : %s, %.2f @ %.2f = %.2f",
            moon.system,
            moon.planet,
            moon.moon,
            moon_yield,
            yields[moon_yield],
            prices[moon_yield],
            cycle_revenue,
        )
        moon_revenue = moon_revenue + cycle_revenue * 24 * 30
    return moon_revenue


@app.task()
def update_moon_revenues():
    logger.info("Updating moon revenue estimates...")

    prices = get_prices()

    moons = EveMoon.objects.all()
    for moon in moons:
        distributions = EveMoonDistribution.objects.filter(moon=moon)
        moon_revenue = calculate_moon_revenue(moon, distributions, prices)
        if moon_revenue is None:
            continue
        logger.debug("Monthly revenue = %.2f", moon_revenue)
        moon.monthly_revenue = moon_revenue
        moon.save()

    logger.info("Moon revenue estimates updated.")
