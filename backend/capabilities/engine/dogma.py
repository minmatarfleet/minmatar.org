"""
A small dogma evaluator for the fitting attributes: can this character
actually fit this fit?

It applies the SDE's effect modifiers the way the game does: skills scale
their bonuses by their trained level, hull skills scale the ship's bonus
attributes, and fitted modules, rigs, subsystems and implants add their own.
Operations run in dogma order with stacking penalties on non-stackable
attributes. Only passive and online effects count, which is all that
matters for CPU, powergrid, calibration and active drones.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from capabilities.engine.sde import (
    ATTR_SKILL_LEVEL,
    CAT_CHARGE,
    CAT_DRONE,
    CAT_FIGHTER,
    CAT_IMPLANT,
    CAT_SHIP,
    CAT_SKILL,
    CAT_SUBSYSTEM,
    CHARACTER_TYPE_ID,
    SdeData,
)

ATTR_CPU_OUTPUT = 48
ATTR_POWER_OUTPUT = 11
ATTR_CPU = 50
ATTR_POWER = 30
ATTR_CALIBRATION = 1132
ATTR_CALIBRATION_COST = 1153
ATTR_MAX_ACTIVE_DRONES = 352
FIT_ATTRS = (
    ATTR_CPU_OUTPUT,
    ATTR_POWER_OUTPUT,
    ATTR_CPU,
    ATTR_POWER,
    ATTR_CALIBRATION,
    ATTR_CALIBRATION_COST,
    ATTR_MAX_ACTIVE_DRONES,
)

EFFECT_PASSIVE = 0
EFFECT_ONLINE = 4
ACTIVE_CATEGORIES = frozenset({EFFECT_PASSIVE, EFFECT_ONLINE})
GROUP_RIG_PREFIX = "Rig "

# Dogma operations, in the order the game applies them.
OP_ORDER = (-1, 0, 1, 2, 3, 4, 5, 6, 7)
PENALIZED_OPS = frozenset({0, 1, 4, 5, 6})
# Bonuses from these categories are never stacking penalized.
PENALTY_EXEMPT = frozenset(
    {CAT_SHIP, CAT_CHARGE, CAT_SKILL, CAT_IMPLANT, CAT_SUBSYSTEM}
)
PENALTY = [math.exp(-((i / 2.67) ** 2)) for i in range(8)]


@dataclass(eq=False)
class Item:
    type_id: int
    kind: str  # ship, module, charge, drone, implant, skill, character
    online: bool = True
    parent: "Item | None" = None  # the module a charge is loaded in
    child: "Item | None" = None  # the charge loaded in a module
    level: int = 0  # skills only


@dataclass
class FitResult:
    cpu_used: float
    cpu_output: float
    power_used: float
    power_output: float
    calibration_used: float
    calibration_output: float
    drones_needed: int
    drones_max: float
    problems: list = field(default_factory=list)

    @property
    def fits(self) -> bool:
        return not self.problems

    @property
    def cpu_short(self) -> float:
        return max(0.0, self.cpu_used - self.cpu_output)

    @property
    def power_short(self) -> float:
        return max(0.0, self.power_used - self.power_output)


@dataclass
class FitItems:
    """What the evaluator needs from a parsed fit."""

    hull: int
    modules: list  # [(type_id, online, charge_type_id | None)]
    drones: list = field(
        default_factory=list
    )  # [(type_id, quantity)] that must launch
    implants: list = field(default_factory=list)


class Dogma:
    def __init__(self, sde: SdeData, fit: FitItems, skills: dict[int, int]):
        self.sde = sde
        self.ship = Item(fit.hull, "ship")
        self.character = Item(CHARACTER_TYPE_ID, "character")
        self.modules: list[Item] = []
        self.charges: list[Item] = []
        for type_id, online, charge in fit.modules:
            module = Item(type_id, "module", online=online)
            self.modules.append(module)
            if charge:
                c = Item(charge, "charge", online=online, parent=module)
                module.child = c
                self.charges.append(c)
        self.drones = [Item(t, "drone") for t, _ in fit.drones]
        self.implants = [Item(t, "implant") for t in fit.implants]
        self.skills = [
            Item(s, "skill", level=lv)
            for s, lv in skills.items()
            if lv > 0 and sde.category(s) == CAT_SKILL
        ]
        self._fit = fit
        self._cache: dict[tuple[int, int], float] = {}
        self.targets: dict[tuple[int, int], list] = {}
        self._index()

    # ------------------------------------------------------------ index
    def _located_on_ship(self):
        return self.modules + self.charges

    def _owned(self):
        return self.drones + self.charges

    def _requires(self, item: Item, skill: int) -> bool:
        return skill in self.sde.required_skills(item.type_id)

    def _sources(self):
        yield self.ship
        yield self.character
        yield from self.skills
        yield from self.implants
        for m in self.modules:
            if m.online:
                yield m
                if m.child:
                    yield m.child
        yield from self.drones

    def _index(self):
        for source in self._sources():
            for _, mod in self.sde.modifiers(
                source.type_id, ACTIVE_CATEGORIES
            ):
                for target in self._resolve_targets(source, mod):
                    self.targets.setdefault(
                        (id(target), mod.modified), []
                    ).append((source, mod))

    def _resolve_targets(self, source: Item, mod):
        func, domain = mod.func, mod.domain
        if func == "ItemModifier":
            if domain == "itemID":
                return [source]
            if domain == "shipID":
                return [self.ship]
            if domain == "charID":
                return [self.character]
            if domain == "otherID":
                other = source.parent or source.child
                return [other] if other else []
            return []
        if domain not in ("shipID", "charID"):
            return []
        if func == "LocationModifier":
            return self._located_on_ship() if domain == "shipID" else []
        if func == "LocationGroupModifier":
            pool = (
                self._located_on_ship()
                if domain == "shipID"
                else self.implants
            )
            return [
                i for i in pool if self.sde.group_id(i.type_id) == mod.group
            ]
        if func in (
            "LocationRequiredSkillModifier",
            "OwnerRequiredSkillModifier",
        ):
            skill = source.type_id if mod.skill in (None, -1) else mod.skill
            if func == "OwnerRequiredSkillModifier":
                pool = self._owned()
            else:
                pool = (
                    self._located_on_ship()
                    if domain == "shipID"
                    else self.implants
                )
            return [i for i in pool if self._requires(i, skill)]
        return []

    # ------------------------------------------------------------ values
    def _base(self, item: Item, attr: int) -> float:
        if item.kind == "skill" and attr == ATTR_SKILL_LEVEL:
            return float(item.level)
        value = self.sde.attrs(item.type_id).get(attr)
        return (
            float(value) if value is not None else self.sde.attr_default(attr)
        )

    def value(self, item: Item, attr: int, depth: int = 0) -> float:
        key = (id(item), attr)
        if key in self._cache:
            return self._cache[key]
        if depth > 25:
            return self._base(item, attr)
        value = self._base(item, attr)
        by_op: dict[int, list] = {}
        for source, mod in self.targets.get(key, ()):
            amount = self.value(source, mod.modifying, depth + 1)
            by_op.setdefault(mod.operation, []).append((source, amount))
        stackable = self.sde.attr_stackable(attr)
        for op in OP_ORDER:
            if by_op.get(op):
                value = self._apply(value, op, by_op[op], stackable)
        self._cache[key] = value
        return value

    def _apply(self, value: float, op: int, entries, stackable: bool) -> float:
        """One dogma operation over every modifier that uses it."""
        if op in (-1, 7):
            return entries[-1][1]
        if op == 2:
            return value + sum(a for _, a in entries)
        if op == 3:
            return value - sum(a for _, a in entries)
        factors, penalized = [], []
        for source, amount in entries:
            f = _factor(op, amount)
            exempt = self.sde.category(source.type_id) in PENALTY_EXEMPT
            if op in PENALIZED_OPS and not stackable and not exempt:
                penalized.append(f)
            else:
                factors.append(f)
        for f in factors:
            value *= f
        for group in (
            sorted((f for f in penalized if f > 1), reverse=True),
            sorted(f for f in penalized if f < 1),
        ):
            for i, f in enumerate(group):
                value *= 1 + (f - 1) * (PENALTY[i] if i < len(PENALTY) else 0)
        return value

    # ------------------------------------------------------------ result
    def _is_rig(self, item: Item) -> bool:
        return self.sde.group_name(item.type_id).startswith(GROUP_RIG_PREFIX)

    def check(self) -> FitResult:
        online = [m for m in self.modules if m.online]
        cpu_used = sum(self.value(m, ATTR_CPU) for m in online)
        power_used = sum(self.value(m, ATTR_POWER) for m in online)
        rigs = [m for m in self.modules if self._is_rig(m)]
        calibration_used = sum(
            self.value(r, ATTR_CALIBRATION_COST) for r in rigs
        )
        drones_needed = min(
            5, max((q for _, q in self._fit.drones), default=0)
        )
        result = FitResult(
            cpu_used=cpu_used,
            cpu_output=self.value(self.ship, ATTR_CPU_OUTPUT),
            power_used=power_used,
            power_output=self.value(self.ship, ATTR_POWER_OUTPUT),
            calibration_used=calibration_used,
            calibration_output=self.value(self.ship, ATTR_CALIBRATION),
            drones_needed=drones_needed,
            drones_max=(
                self.value(self.character, ATTR_MAX_ACTIVE_DRONES)
                if drones_needed
                else 0
            ),
        )
        # Rounding margin: the client shows two decimals.
        if result.cpu_used > result.cpu_output + 0.005:
            result.problems.append("cpu")
        if result.power_used > result.power_output + 0.005:
            result.problems.append("power")
        if result.calibration_used > result.calibration_output + 0.005:
            result.problems.append("calibration")
        if drones_needed and result.drones_max + 1e-9 < drones_needed:
            result.problems.append("drones")
        return result


def _factor(op: int, amount: float) -> float:
    if op in (0, 4):
        return amount
    if op in (1, 5):
        return 1 / amount if amount else 1.0
    return 1 + amount / 100


def check_fit(
    sde: SdeData, fit: FitItems, skills: dict[int, int]
) -> FitResult:
    return Dogma(sde, fit, skills).check()


def fitting_skill_ids(sde: SdeData, fit: FitItems) -> set[int]:
    """Skills that reach a fitting attribute of this fit, directly or not.

    Hull skills count through the ship's bonus attributes they scale, so
    the walk follows every modifying attribute back to its sources.
    """
    all_v = {
        s: 5
        for s, (_, g) in sde.types.items()
        if sde.groups.get(g, ["", 0])[1] == CAT_SKILL
    }
    d = Dogma(sde, fit, all_v)
    found: set[int] = set()
    seen: set[tuple[int, int]] = set()
    stack = [
        (t, attr)
        for t in [d.ship, d.character] + d.modules
        for attr in FIT_ATTRS
    ]
    while stack:
        item, attr = stack.pop()
        key = (id(item), attr)
        if key in seen:
            continue
        seen.add(key)
        for source, mod in d.targets.get(key, ()):
            if source.kind == "skill":
                found.add(source.type_id)
            stack.append((source, mod.modifying))
    return found


__all__ = [
    "CAT_DRONE",
    "CAT_FIGHTER",
    "Dogma",
    "FitItems",
    "FitResult",
    "check_fit",
    "fitting_skill_ids",
]
