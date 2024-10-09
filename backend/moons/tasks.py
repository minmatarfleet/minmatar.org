import logging
import requests
from app.celery import app
from decimal import Decimal

from moons.models import EveMoon, EveMoonDistribution, ore_yield_map
from moons.helpers import calc_metanox_yield

logger = logging.getLogger(__name__)


def item_id(item_name: str, product_ids) -> str:
    for product in product_ids:
        if product["name"] == item_name:
            return product["id"]
    return -1


def get_prices():
    logger.info("Fetching moon product prices...")

    prices = {}
    for ore in ore_yield_map:
        for item in ore_yield_map[ore]:
            prices[item] = Decimal(0)

    products = []
    for item in prices:
        products.append(item)

    base_url = "https://esi.evetech.net/latest"

    response = requests.post(url=base_url + "/universe/ids", json=products, timeout=5)
    product_ids = response.json()["inventory_types"]
    # logger.info(product_ids)

    for price in prices:
        type_id = item_id(price, product_ids)
        url = base_url + "/markets/10000002/history?type_id=" + str(type_id)
        response = requests.get(url, timeout=5)
        data = response.json()[0]["average"]
        logger.info("%s value = %.2f", price, data)
        prices[price] = Decimal(data)

    logger.info("Moon product prices retrieved.")

    return prices


def calculate_moon_revenue(moon, distributions, prices):
    yields = calc_metanox_yield(distributions)
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
        logger.info("Monthly revenue = %.2f", moon_revenue)
        moon.monthly_revenue = moon_revenue
        moon.save()

    logger.info("Moon revenue estimates updated.")
