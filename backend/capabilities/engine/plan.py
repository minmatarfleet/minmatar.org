"""Training plans: the skill levels to queue, in an order EVE accepts.

Pure python on plain dicts, so a request can build one from stored rows
without loading the SDE.
"""

from __future__ import annotations

from dataclasses import dataclass

from capabilities.engine import rules
from capabilities.engine.requirements import SP_TOTAL

ROMAN = ("", "I", "II", "III", "IV", "V")


@dataclass(frozen=True)
class Step:
    skill: int
    level: int
    days: float


def step_days(rank: float, level: int, trained_sp: int = 0) -> float:
    """Days to train one level, less the skill points already in it."""
    sp = SP_TOTAL[level] * rank - max(trained_sp, SP_TOTAL[level - 1] * rank)
    return max(sp, 0) / rules.SP_PER_HOUR / 24


def with_prerequisites(
    targets: dict[int, int], prerequisites: dict[int, dict[int, int]]
) -> dict[int, int]:
    out = dict(targets)
    stack = list(targets)
    while stack:
        for pre, level in prerequisites.get(stack.pop(), {}).items():
            if out.get(pre, 0) < level:
                out[pre] = level
                stack.append(pre)
    return out


def plan(
    targets: dict[int, int],
    skills: dict[int, int],
    ranks: dict[int, float],
    prerequisites: dict[int, dict[int, int]],
    trained_sp: dict[int, int] | None = None,
) -> list[Step]:
    """Every missing level of the targets and their prerequisites.

    The cheapest step goes first, but never before the level under it or a
    prerequisite the skill needs.
    """
    trained_sp = trained_sp or {}
    want = with_prerequisites(targets, prerequisites)
    have = {s: skills.get(s, 0) for s in want}
    pending = {
        (s, level)
        for s, lv in want.items()
        for level in range(have[s] + 1, lv + 1)
    }

    def days(s, level):
        sp = trained_sp.get(s, 0) if level == have[s] + 1 else 0
        return step_days(ranks.get(s, 1.0), level, sp)

    def available(s, level):
        if (s, level - 1) in pending:
            return False
        return all(
            (pre, lv) not in pending
            for pre, need in prerequisites.get(s, {}).items()
            for lv in range(1, need + 1)
        )

    steps = []
    while pending:
        ready = [p for p in pending if available(*p)] or list(pending)
        s, level = min(ready, key=lambda p: (days(*p), p[1], p[0]))
        pending.discard((s, level))
        steps.append(Step(s, level, round(days(s, level), 2)))
    return steps


def total_days(steps: list[Step]) -> float:
    return round(sum(step.days for step in steps), 2)


def eve_text(steps: list[Step], names: dict[int, str]) -> str:
    """One "Skill Name IV" line per level: EVE's skill queue pastes this."""
    return "\n".join(
        f"{names.get(step.skill, step.skill)} {ROMAN[step.level]}"
        for step in steps
    )
