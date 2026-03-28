"""3-character public codes for industry orders (Discord display); unique among active orders."""

from __future__ import annotations

import secrets
import string

from industry.models import IndustryOrder

_ALPHABET = string.ascii_letters + string.digits
_CODE_LEN = 3
_MAX_ATTEMPTS = 256


def generate_random_public_short_code(length: int = _CODE_LEN) -> str:
    """Return a random string of ``length`` from a-z, A-Z, 0-9."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def pick_unique_public_short_code_among_actives(
    *,
    exclude_order_pk: int | None = None,
) -> str:
    """
    Random candidate until no other *active* order (``fulfilled_at`` null) uses it.
    Fulfilled orders may reuse codes; we only check actives.
    """
    for _ in range(_MAX_ATTEMPTS):
        candidate = generate_random_public_short_code()
        qs = IndustryOrder.objects.filter(
            public_short_code=candidate,
            fulfilled_at__isnull=True,
        )
        if exclude_order_pk is not None:
            qs = qs.exclude(pk=exclude_order_pk)
        if not qs.exists():
            return candidate
    raise RuntimeError(
        "Could not allocate a unique public_short_code among active orders."
    )


def is_valid_public_short_code(value: str) -> bool:
    if not value or len(value) != _CODE_LEN:
        return False
    return all(c in _ALPHABET for c in value)


def public_short_code_taken_by_active(
    code: str,
    *,
    exclude_order_pk: int | None = None,
) -> bool:
    qs = IndustryOrder.objects.filter(
        public_short_code=code,
        fulfilled_at__isnull=True,
    )
    if exclude_order_pk is not None:
        qs = qs.exclude(pk=exclude_order_pk)
    return qs.exists()
