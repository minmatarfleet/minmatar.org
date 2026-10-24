"""Staging supply readiness levels for doctrine contract stock."""

from __future__ import annotations

from typing import Literal

ReadinessLevel = Literal["ready", "thin", "empty", "unknown"]


def fitting_readiness(
    current_quantity: int,
    expectation_quantity: int | None,
) -> ReadinessLevel:
    """Readiness for a single fitting at a staging."""
    if expectation_quantity is None or expectation_quantity <= 0:
        return "unknown"
    if current_quantity <= 0:
        return "empty"
    if current_quantity >= expectation_quantity:
        return "ready"
    return "thin"


def shortfall(current_quantity: int, expectation_quantity: int | None) -> int:
    if expectation_quantity is None or expectation_quantity <= 0:
        return 0
    return max(0, expectation_quantity - current_quantity)
