"""Stable tribe catalog codes shared across reports, scripts, and APIs."""

# supply.production is the live group. The older codes still count a
# member if the merge has not run.
MANUFACTURING_PRODUCTION_GROUP_CODES = frozenset(
    {
        "supply.production",
        "supply.subcapital-production",
        "supply.capital-production",
        "industry.subcapital-production",
        "industry.capital-production",
    }
)
