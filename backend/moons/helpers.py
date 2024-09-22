from .models import ore_yield_map


# 30k m3 per hour from an athanor for base calculation
def get_athanor_yield():
    """
    Return the hourly yield of an Athanor
    """
    return {
        "Hydrocarbons": 65,
        "Pyerite": 6000,
        "Mexallon": 400,
    }


def get_metanox_yield():
    """
    Return the hourly yield of Metanox mining
    40% of the yield of an Athanor
    """
    return {
        "Hydrocarbons": 65,
        "Pyerite": 6000,
        "Mexallon": 400,
    }


def calc_metanox_yield(distributions):
    """Returns the product yields from a Metanox drill using the specified moon ore distributions."""
    yields = {}
    yield_factor = 0.4 * 30000 / 1000
    for distr in distributions:
        yield_map = ore_yield_map[distr.ore]
        for product in yield_map:
            yields[product] = (
                distr.yield_percent * yield_factor * yield_map[product]
            )

    return yields
