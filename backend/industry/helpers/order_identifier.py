"""Human-readable unique identifiers for industry orders (e.g. big-iron-hands)."""

import re
import secrets

# Short word list for auto-generated three-part slugs (adj-noun-verb style mix).
_IDENTIFIER_WORDS = (
    "iron",
    "blue",
    "red",
    "gold",
    "swift",
    "deep",
    "cold",
    "wild",
    "big",
    "old",
    "new",
    "high",
    "low",
    "dark",
    "bright",
    "hands",
    "stars",
    "void",
    "forge",
    "rails",
    "core",
    "edge",
    "prime",
    "delta",
    "gamma",
    "sigma",
    "omega",
    "hawk",
    "wolf",
    "bear",
    "storm",
    "frost",
    "ember",
    "tide",
    "flux",
)

ORDER_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+){2}$")


def validate_order_identifier(raw: str) -> str:
    s = raw.strip().lower()
    if not ORDER_IDENTIFIER_PATTERN.match(s):
        raise ValueError(
            "order_identifier must be three lowercase segments separated by hyphens "
            "(e.g. big-iron-hands)."
        )
    return s


def generate_random_order_identifier() -> str:
    return "-".join(secrets.choice(_IDENTIFIER_WORDS) for _ in range(3))
