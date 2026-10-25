"""How ready one character is for one fitting."""

from __future__ import annotations

from dataclasses import dataclass, field

from capabilities.engine import rules
from capabilities.engine.dogma import check_fit, fitting_skill_ids
from capabilities.engine.fit import ParsedFit
from capabilities.engine.requirements import Requirements, meets, train_days
from capabilities.engine.sde import SdeData


@dataclass
class Readiness:
    unlocked: bool
    hard_ready: bool
    core_ready: bool
    missing_required: list = field(
        default_factory=list
    )  # [[skill, have, need]]
    missing_core: list = field(default_factory=list)
    fit_problems: list = field(
        default_factory=list
    )  # cpu / power / calibration / drones
    days_to_hard: float = 0.0
    days_to_core: float = 0.0
    support_score: int = 0


class FitChecker:
    """Exact fit checks for one fitting, memoized on the levels that matter.

    The result only depends on a character's levels of the skills that touch
    CPU, grid, calibration or drone count (usually about ten), so most of
    the alliance shares a handful of answers.
    """

    def __init__(self, sde: SdeData, fit: ParsedFit, req: Requirements):
        self.sde = sde
        self.fit = fit
        self.req = req
        self._relevant: dict[tuple, list[int]] = {}
        self._memo: dict[tuple, list[str]] = {}

    def _skill_ids(self, substitutes: tuple) -> list[int]:
        if substitutes not in self._relevant:
            items = self.fit.fit_items(dict(substitutes))
            self._relevant[substitutes] = sorted(
                fitting_skill_ids(self.sde, items)
            )
        return self._relevant[substitutes]

    def problems(
        self, skills: dict[int, int], substitutes: dict[int, int]
    ) -> list[str]:
        subs = tuple(sorted(substitutes.items()))
        ids = self._skill_ids(subs)
        key = (subs, tuple(skills.get(s, 0) for s in ids))
        if key not in self._memo:
            relevant = {s: skills.get(s, 0) for s in ids}
            self._memo[key] = check_fit(
                self.sde, self.fit.fit_items(dict(subs)), relevant
            ).problems
        return self._memo[key]


def _pick_substitutes(req: Requirements, skills: dict[int, int]):
    """For each substituted slot, the first module the character can use."""
    chosen, missing = {}, {}
    for preferred, subs in req.alternatives.items():
        options = [preferred] + list(subs)
        usable = [
            m
            for m in options
            if meets(skills, req.alternative_requirements[m])
        ]
        if usable:
            if usable[0] != preferred:
                chosen[preferred] = usable[0]
        else:
            for s, lv in req.alternative_requirements[preferred].items():
                if skills.get(s, 0) < lv:
                    missing[s] = max(missing.get(s, 0), lv)
    return chosen, missing


def evaluate(
    sde: SdeData,
    req: Requirements,
    checker: FitChecker,
    hull_requirements: dict[int, int],
    skills: dict[int, int],
) -> Readiness:
    unlocked = meets(skills, hull_requirements)
    required = req.required()
    chosen, alt_missing = _pick_substitutes(req, skills)
    missing_required = [
        [s, skills.get(s, 0), lv]
        for s, lv in required.items()
        if skills.get(s, 0) < lv
    ]
    for s, lv in alt_missing.items():
        if not any(m[0] == s for m in missing_required):
            missing_required.append([s, skills.get(s, 0), lv])
    fit_problems = checker.problems(skills, chosen) if unlocked else ["hull"]
    hard_ready = unlocked and not missing_required and not fit_problems

    core = req.core()
    # A skill can be required at one level and core at a higher one
    # (Amarr Dreadnought I to fly a Revelation, IV for core): only the part
    # the required check already reports is left out.
    missing_core = [
        [s, skills.get(s, 0), lv]
        for s, lv in core.items()
        if skills.get(s, 0) < lv and required.get(s, 0) < lv
    ]
    core_ready = hard_ready and not missing_core

    def days(missing):
        return round(
            sum(train_days(sde, s, have, need) for s, have, need in missing), 2
        )

    # The fit plan levels show how far a pilot is from fitting it.
    plan_missing = [
        [s, skills.get(s, 0), r.fit_level]
        for s, r in req.rows.items()
        if r.fit_level and skills.get(s, 0) < r.fit_level
    ]
    days_to_hard = days(missing_required) + (
        days(plan_missing) if fit_problems else 0
    )

    total = achieved = 0.0
    for s, r in req.rows.items():
        if not r.optimal_level or not r.per_level:
            continue
        w = r.weight
        total += w * r.optimal_level
        achieved += w * min(skills.get(s, 0), r.optimal_level)
    score = round(100 * achieved / total) if total else 100

    return Readiness(
        unlocked=unlocked,
        hard_ready=hard_ready,
        core_ready=core_ready,
        missing_required=sorted(
            missing_required
            + [
                m
                for m in plan_missing
                if fit_problems and m[0] not in required
            ]
        ),
        missing_core=sorted(missing_core),
        fit_problems=fit_problems if unlocked else [],
        days_to_hard=round(days_to_hard, 2),
        days_to_core=round(days_to_hard + days(missing_core), 2),
        support_score=score,
    )


def train_next(
    sde: SdeData, req: Requirements, skills: dict[int, int], limit=5
):
    """R14: the missing levels worth the most per training day."""
    out = []
    for s, r in req.rows.items():
        target = (
            max(r.required_level, r.fit_level, r.core_level) or r.optimal_level
        )
        have = skills.get(s, 0)
        if have >= target or not r.per_level:
            continue
        days = train_days(sde, s, have, target)
        gain = r.weight * (target - have)
        out.append(
            (
                gain / max(days, rules.MIN_TRAIN_DAYS),
                s,
                have,
                target,
                round(days, 2),
            )
        )
    out.sort(reverse=True)
    return [
        {"skill": s, "have": h, "want": t, "days": d}
        for _, s, h, t, d in out[:limit]
    ]
