"""
Guard: member-facing ISK values use the pricing helpers, not CCP averages.

docs/market-pricing.md keeps ``EveMarketPrice`` (CCP's universe average) for
EIV, availability filters and as the fallback inside the history helpers.
Anything else should call market.helpers.pricing (guide) or the industry
Jita sell helpers. Add a file here only with a reason.
"""

import ast
from pathlib import Path

from django.test import SimpleTestCase

BACKEND = Path(__file__).resolve().parents[2]

ALLOWED = {
    # Guide helpers: history first, EveMarketPrice fallback.
    "market/helpers/pricing.py",
    # Estimated item value (EIV) for job cost uses CCP adjusted prices.
    "industry/helpers/build_planner.py",
    # "Has any market" filter for compressed ore candidates.
    "industry/helpers/compressed_ore.py",
}


def _uses_eve_market_price(source: str) -> bool:
    """True when code (not a comment or docstring) names EveMarketPrice."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name) and node.id == "EveMarketPrice":
            return True
        if isinstance(node, ast.alias) and node.name == "EveMarketPrice":
            return True
    return False


class EveMarketPriceReadersTestCase(SimpleTestCase):
    def test_only_allowed_modules_read_ccp_average_prices(self):
        found = set()
        for path in BACKEND.rglob("*.py"):
            rel = path.relative_to(BACKEND).as_posix()
            parts = rel.split("/")
            if (
                any(part.startswith(".") for part in parts)
                or "site-packages" in parts
                or "tests" in parts
                or "migrations" in parts
                or "management" in parts
                or parts[-1].startswith("test")
            ):
                continue
            if _uses_eve_market_price(path.read_text(encoding="utf-8")):
                found.add(rel)
        self.assertEqual(found - ALLOWED, set())
