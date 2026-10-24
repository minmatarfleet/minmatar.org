import decimal

from .models import ore_yield_map


def calc_metanox_yield(distributions):
    """Returns the product yields from a Metanox drill using the specified moon ore distributions."""
    yields = {}
    yield_factor = decimal.Decimal(0.4 * 30000 / 1000)
    for distr in distributions:
        yield_map = ore_yield_map[distr.ore]
        for product in yield_map:
            # Several ores can make the same product (Pyerite, Mexallon...).
            yields[product] = yields.get(product, 0) + (
                distr.yield_percent * yield_factor * yield_map[product]
            )

    return yields
