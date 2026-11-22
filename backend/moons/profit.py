"""What a moon earns a month with a Metenox Moon Drill, after fuel.

A Metenox burns Magmatic Gas and fuel blocks every hour whatever the moon
holds, so the fuel bill is the same for every moon. Net a month is the
output value minus that bill.
"""

from __future__ import annotations

from decimal import Decimal

from moons.helpers import calc_metanox_yield

HOURS_A_MONTH = 24 * 30

# Metenox Moon Drill fuel use per hour.
MAGMATIC_GAS = "Magmatic Gas"
MAGMATIC_GAS_PER_HOUR = 200
FUEL_BLOCKS_PER_HOUR = 5
# Any racial block runs it, so the cheapest one is priced.
FUEL_BLOCKS = (
    "Nitrogen Fuel Block",
    "Hydrogen Fuel Block",
    "Helium Fuel Block",
    "Oxygen Fuel Block",
)
FUEL_TYPE_NAMES = (MAGMATIC_GAS, *FUEL_BLOCKS)


def _line(name: str, units: Decimal, price: Decimal) -> dict:
    return {
        "name": name,
        "units": int(round(units)),
        "price": float(price),
        "isk": int(round(units * price)),
    }


def fuel_lines(prices: dict[str, Decimal]) -> list[dict] | None:
    """A month of Metenox fuel, or None when gas or every block is unpriced."""
    gas_price = prices.get(MAGMATIC_GAS)
    blocks = [(name, prices[name]) for name in FUEL_BLOCKS if name in prices]
    if gas_price is None or not blocks:
        return None
    block_name, block_price = min(blocks, key=lambda item: item[1])
    return [
        _line(
            MAGMATIC_GAS,
            Decimal(MAGMATIC_GAS_PER_HOUR * HOURS_A_MONTH),
            gas_price,
        ),
        _line(
            block_name,
            Decimal(FUEL_BLOCKS_PER_HOUR * HOURS_A_MONTH),
            block_price,
        ),
    ]


def output_lines(distributions, prices) -> list[dict] | None:
    """A month of drill output, or None when a product has no price."""
    yields = calc_metanox_yield(distributions)
    if any(product not in prices for product in yields):
        return None
    lines = [
        _line(product, per_hour * HOURS_A_MONTH, prices[product])
        for product, per_hour in yields.items()
    ]
    return sorted(lines, key=lambda line: -line["isk"])


def profit_breakdown(distributions, prices) -> dict | None:
    """Output, fuel and net a month for one moon.

    None when an output product has no price. When only fuel is unpriced,
    `fuel` is empty and `net` is None.
    """
    output = output_lines(distributions, prices)
    if output is None:
        return None
    fuel = fuel_lines(prices)
    revenue = sum(line["isk"] for line in output)
    fuel_cost = sum(line["isk"] for line in fuel) if fuel else None
    return {
        "output": output,
        "fuel": fuel or [],
        "revenue": revenue,
        "fuel_cost": fuel_cost,
        "net": revenue - fuel_cost if fuel_cost is not None else None,
    }
