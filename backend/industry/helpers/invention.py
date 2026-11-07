"""Invention maths for T2 and T3 blueprint copies. Pure: no database access.

An invention attempt consumes one source (a T1 blueprint copy run or an
ancient relic), its datacores and an optional decryptor, whether it succeeds
or not. A success yields one copy with ``runs`` runs at ME 2 / TE 4, adjusted
by the decryptor. ``choose`` compares every source and decryptor on the full
cost of the units asked for: invention plus the root build, because a
decryptor's ME and runs change the build's material bill.

Costs are expected values and amortise copy runs: a 10-run copy used for one
unit charges a tenth of the expected attempts, since the leftover runs build
the next lot. The buy list rounds up to whole attempts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

# Every invented copy starts at ME 2 / TE 4 (percent) before decryptors.
BASE_COPY_ME = 2
BASE_COPY_TE = 4

AUTO = "auto"
NONE = "none"


@dataclass(frozen=True)
class InventionSkills:
    """Skill levels that change invention chance and science job times."""

    science_1: int = 5
    science_2: int = 5
    encryption: int = 4
    # Advanced Industry: -3% invention time per level.
    advanced_industry: int = 5
    # Science: -5% copy time per level.
    science: int = 5

    def chance_multiplier(self) -> float:
        return (
            1.0
            + (self.science_1 + self.science_2) / 30.0
            + (self.encryption / 40.0)
        )


@dataclass(frozen=True)
class DecryptorOption:
    """A decryptor (or none) with its Jita price."""

    type_id: Optional[int]
    name: str
    probability_multiplier: float = 1.0
    runs_modifier: int = 0
    me_modifier: int = 0
    te_modifier: int = 0
    unit_price: float = 0.0


NO_DECRYPTOR = DecryptorOption(type_id=None, name="No decryptor")


@dataclass(frozen=True)
class AttemptInput:
    """Something one attempt consumes."""

    type_id: int
    name: str
    quantity: int
    unit_price: float


@dataclass(frozen=True)
class FeeParts:
    """One job's install fee, split the way the cost breakdown reports it."""

    gross: int = 0
    facility_tax: int = 0
    scc: int = 0

    @property
    def total(self) -> int:
        return self.gross + self.facility_tax + self.scc


@dataclass(frozen=True)
class SourceOption:
    """One invention outcome (T1 blueprint or relic → this product) with prices."""

    source_type_id: int
    source_name: str
    source_kind: str
    base_probability: float
    base_runs: int
    # Datacores, and the relic itself for T3.
    inputs: Tuple[AttemptInput, ...]
    invention_fee: FeeParts
    copy_fee: FeeParts = FeeParts()
    invention_seconds: float = 0.0
    copy_seconds: float = 0.0


@dataclass(frozen=True)
class InventionQuote:
    """One source × decryptor choice, costed for ``units`` of the product."""

    source: SourceOption
    decryptor: DecryptorOption
    chance: float
    runs_per_copy: int
    copy_me: int
    copy_te: int
    units: int
    runs_needed: int
    copies_needed: float
    expected_attempts: float
    buy_attempts: int
    attempts_p90: int
    inputs_isk_per_attempt: float
    decryptor_isk_per_attempt: float
    fee_isk_per_attempt: float
    invention_materials_isk: float
    invention_job_costs_isk: float
    invention_facility_tax_isk: float
    invention_scc_isk: float
    build_isk: float
    science_seconds: float

    @property
    def attempt_isk(self) -> float:
        return (
            self.inputs_isk_per_attempt
            + self.decryptor_isk_per_attempt
            + self.fee_isk_per_attempt
        )

    @property
    def invention_isk(self) -> float:
        return self.invention_materials_isk + self.invention_job_costs_isk

    @property
    def total_isk(self) -> float:
        return self.invention_isk + self.build_isk

    @property
    def per_unit_isk(self) -> float:
        return self.total_isk / max(self.units, 1)

    @property
    def invention_per_unit_isk(self) -> float:
        return self.invention_isk / max(self.units, 1)


@dataclass
class InventionChoice:
    """The cheapest quote plus the others, cheapest first."""

    best: InventionQuote
    alternatives: List[InventionQuote] = field(default_factory=list)


def success_chance(
    base_probability: float,
    skills: InventionSkills,
    probability_multiplier: float = 1.0,
) -> float:
    """``base × (1 + (sci₁ + sci₂)/30 + encryption/40) × decryptor``, capped at 1."""
    chance = (
        float(base_probability)
        * skills.chance_multiplier()
        * float(probability_multiplier)
    )
    return max(0.0, min(1.0, chance))


def attempts_for_confidence(
    successes: int, chance: float, confidence: float = 0.9
) -> int:
    """Fewest attempts that give ``successes`` successes with this confidence."""
    if successes <= 0:
        return 0
    if chance >= 1.0:
        return successes
    if chance <= 0.0:
        raise ValueError("chance must be positive")
    if successes > 400:
        # Normal approximation to the negative binomial for big lots.
        mean = successes / chance
        stdev = math.sqrt(successes * (1 - chance)) / chance
        return int(math.ceil(mean + 1.2816 * stdev))
    attempts = successes
    while True:
        # P(at least `successes` in `attempts` tries)
        q = 1.0 - chance
        below = sum(
            math.comb(attempts, k) * chance**k * q ** (attempts - k)
            for k in range(successes)
        )
        if 1.0 - below >= confidence:
            return attempts
        attempts += 1


def quote(
    *,
    source: SourceOption,
    decryptor: DecryptorOption,
    skills: InventionSkills,
    units: int,
    products_per_run: int,
    build_cost: Callable[[float, int], float],
) -> InventionQuote:
    """Cost ``units`` of the product invented from ``source`` with ``decryptor``.

    ``build_cost(me_fraction, runs_per_copy)`` returns the ISK of the root
    manufacturing job(s) for those units at that copy ME and run cap.
    """
    units = max(int(units), 1)
    per_run = max(int(products_per_run), 1)
    chance = success_chance(
        source.base_probability, skills, decryptor.probability_multiplier
    )
    if chance <= 0:
        raise ValueError(f"{source.source_name}: zero invention chance")
    runs_per_copy = max(1, source.base_runs + int(decryptor.runs_modifier))
    copy_me = BASE_COPY_ME + int(decryptor.me_modifier)
    copy_te = BASE_COPY_TE + int(decryptor.te_modifier)
    runs_needed = int(math.ceil(units / per_run))
    copies_needed = runs_needed / runs_per_copy
    expected_attempts = copies_needed / chance
    whole_copies = int(math.ceil(copies_needed))
    buy_attempts = int(math.ceil(whole_copies / chance - 1e-9))

    inputs_isk = sum(i.quantity * i.unit_price for i in source.inputs)
    decryptor_isk = float(decryptor.unit_price) if decryptor.type_id else 0.0
    fees = (source.invention_fee, source.copy_fee)
    fee_isk = float(sum(f.total for f in fees))
    return InventionQuote(
        source=source,
        decryptor=decryptor,
        chance=chance,
        runs_per_copy=runs_per_copy,
        copy_me=copy_me,
        copy_te=copy_te,
        units=units,
        runs_needed=runs_needed,
        copies_needed=copies_needed,
        expected_attempts=expected_attempts,
        buy_attempts=buy_attempts,
        attempts_p90=attempts_for_confidence(whole_copies, chance),
        inputs_isk_per_attempt=inputs_isk,
        decryptor_isk_per_attempt=decryptor_isk,
        fee_isk_per_attempt=fee_isk,
        invention_materials_isk=expected_attempts
        * (inputs_isk + decryptor_isk),
        invention_job_costs_isk=expected_attempts * fee_isk,
        invention_facility_tax_isk=expected_attempts
        * sum(f.facility_tax for f in fees),
        invention_scc_isk=expected_attempts * sum(f.scc for f in fees),
        build_isk=float(build_cost(copy_me / 100.0, runs_per_copy)),
        science_seconds=expected_attempts
        * (source.invention_seconds + source.copy_seconds),
    )


def choose(
    *,
    sources: Sequence[SourceOption],
    decryptors: Iterable[DecryptorOption],
    skills: InventionSkills,
    units: int,
    products_per_run: int,
    build_cost: Callable[[float, int], float],
) -> InventionChoice:
    """Quote every source × decryptor; the cheapest per unit wins."""
    options = list(decryptors)
    quotes = [
        quote(
            source=source,
            decryptor=decryptor,
            skills=skills,
            units=units,
            products_per_run=products_per_run,
            build_cost=build_cost,
        )
        for source in sources
        for decryptor in options
    ]
    if not quotes:
        raise ValueError("No invention source or decryptor to quote")
    quotes.sort(
        key=lambda q: (
            q.per_unit_isk,
            q.decryptor.type_id is not None,
            q.source.source_type_id,
        )
    )
    return InventionChoice(best=quotes[0], alternatives=quotes[1:])
