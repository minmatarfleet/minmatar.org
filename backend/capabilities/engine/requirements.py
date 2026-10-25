"""
Layered skill requirements for one doctrine fitting.

    required  what the fit needs to fit and fly (R3, R4, R17)
    core      support skills a pilot needs to be Doctrine-ready (R8-R10)
    optimal   support skills worth taking further (R11)

Pure Python over an SdeData snapshot; the Celery tasks feed it fleet seats
and skills and store the result. See docs/capabilities/capability-engine-design.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from capabilities.engine import rules
from capabilities.engine.dogma import check_fit, fitting_skill_ids
from capabilities.engine.fit import ParsedFit
from capabilities.engine.sde import CAT_DRONE, CAT_FIGHTER, SdeData

SP_TOTAL = (0, 250, 1415, 8000, 45255, 256000)

ARMOR_ATTRS = frozenset({265, 267, 268, 269, 270})
SHIELD_ATTRS = frozenset({263, 479, 271, 272, 273, 274})
HULL_HP_ATTRS = frozenset({9, 109, 110, 111, 113})
HULL_BUCKETS = {
    37: "navigation",
    70: "navigation",
    552: "navigation",
    4: "navigation",
    482: "capacitor",
    55: "capacitor",
    76: "targeting",
    564: "targeting",
    192: "targeting",
    48: "fitting",
    11: "fitting",
    1132: "fitting",
    867: "jump",
    868: "jump",
    898: "jump",
    283: "drones",
    1271: "drones",
}
ITEM_ATTR_BUCKETS = {
    50: "fitting",
    30: "fitting",
    1153: "fitting",
    6: "capacitor",
}
CHAR_BUCKETS = {212: "targeting", 352: "drones"}

EWAR_WORDS = (
    "ecm",
    "sensor dampener",
    "weapon disruptor",
    "stasis web",
    "energy neutralizer",
    "target painter",
)
TACKLE_WORDS = ("warp scrambler", "warp disrupt", "interdiction sphere")
_BURST_RE = re.compile(r"Command Burst|Mining Foreman Burst")
_REMOTE_RE = re.compile(
    r"Remote (Armor Repairer|Shield Booster|Hull Repairer|Capacitor Transmitter)"
)
_TAGS_RE = re.compile(r"<[^>]+>")


# ---------------------------------------------------------------- helpers
def train_days(sde: SdeData, skill: int, have: int, want: int) -> float:
    if want <= have:
        return 0.0
    sp = (SP_TOTAL[want] - SP_TOTAL[have]) * sde.skill_rank(skill)
    return sp / rules.SP_PER_HOUR / 24


def meets(skills: dict[int, int], req: dict[int, int]) -> bool:
    return all(skills.get(s, 0) >= lv for s, lv in req.items())


def hard_requirements(sde: SdeData, types) -> dict[int, int]:
    out: dict[int, int] = {}
    for tid in types:
        for s, lv in sde.required_skills(tid).items():
            out[s] = max(out.get(s, 0), lv)
    return sde.with_prerequisites(out)


def tank_layers(sde: SdeData, fit: ParsedFit) -> set[str]:
    armor = shield = 0
    for m in fit.module_ids:
        g = sde.group_name(m).lower()
        armor += "armor" in g
        shield += "shield" in g
    if armor == shield == 0:
        a = sde.attrs(fit.hull)
        return {"armor"} if a.get(265, 0) >= a.get(263, 0) else {"shield"}
    layers = set()
    if armor >= shield:
        layers.add("armor")
    if shield >= armor:
        layers.add("shield")
    return layers


def item_bucket(sde: SdeData, item: int, attr: int) -> str:
    if attr in ITEM_ATTR_BUCKETS:
        return ITEM_ATTR_BUCKETS[attr]
    g = sde.group_name(item).lower()
    if sde.category(item) in (CAT_DRONE, CAT_FIGHTER):
        return "drones"
    if any(w in g for w in ("remote", "burst", "command")) or any(
        w in g for w in EWAR_WORDS + ("warp scram", "nosferatu")
    ):
        return "support"
    if "propulsion" in g or "micro jump" in g:
        return "navigation"
    if any(w in g for w in ("armor", "shield", "damage control", "hull")):
        return "tank"
    if "capacitor" in g:
        return "capacitor"
    if "jump" in g or "cyno" in g:
        return "jump"
    if "sensor" in g:
        return "targeting"
    return "damage"


def trait_bucket(text: str) -> str:
    t = text.lower()
    for words, bucket in (
        (
            (
                "resist",
                "armor hit",
                "shield hit",
                "hitpoint",
                "repair amount",
                "armor repair",
                "shield boost",
            ),
            "tank",
        ),
        (
            (
                "burst",
                "command",
                "remote",
                "ecm",
                "warp disruption",
                "web",
                "neutralizer",
                "jamming",
                "sensor dampener",
            ),
            "support",
        ),
        (("activation cost", "capacitor"), "capacitor"),
        (("velocity", "agility", "speed"), "navigation"),
        (("jump", "fuel"), "jump"),
        (("drone",), "drones"),
    ):
        if any(w in t for w in words):
            return bucket
    return "damage"


@dataclass
class Touch:
    bucket: str
    per_level: float
    why: str


def _item_touch(sde, m, value, items, match) -> "Touch | None":
    hits = [i for i in items if match(i) and sde.attrs(i).get(m.modified)]
    if not hits:
        return None
    return Touch(
        item_bucket(sde, hits[0], m.modified),
        value,
        f"{sde.attr_name(m.modified)} of {sde.name(hits[0])}",
    )


def _hull_touch(sde, m, value, fit, layers) -> "Touch | None":
    if m.modified in ARMOR_ATTRS and "armor" not in layers:
        return None
    if m.modified in SHIELD_ATTRS and "shield" not in layers:
        return None
    why = f"hull {sde.attr_name(m.modified)}"
    if m.modified in ARMOR_ATTRS | SHIELD_ATTRS | HULL_HP_ATTRS:
        return Touch("tank", value, why)
    if m.modified in HULL_BUCKETS and sde.attrs(fit.hull).get(m.modified):
        return Touch(HULL_BUCKETS[m.modified], value, why)
    return None


def _pilot_touch(sde, m, value, fit) -> "Touch | None":
    bucket = CHAR_BUCKETS.get(m.modified)
    if not bucket or (bucket == "drones" and not fit.drones):
        return None
    return Touch(bucket, value, f"pilot {sde.attr_name(m.modified)}")


def touches(
    sde: SdeData, skill: int, fit: ParsedFit, layers: set[str]
) -> list[Touch]:
    """R6: how a skill's modifiers reach this fit."""
    items = fit.items()
    skill_attrs = sde.attrs(skill)
    out = []
    for _, m in sde.modifiers(skill):
        value = abs(skill_attrs.get(m.modifying, 0.0))
        touch = None
        if m.func in (
            "LocationRequiredSkillModifier",
            "OwnerRequiredSkillModifier",
        ):
            target = skill if m.skill in (None, -1) else m.skill
            touch = _item_touch(
                sde,
                m,
                value,
                items,
                lambda i, t=target: t in sde.required_skills(i),
            )
        elif m.func == "LocationGroupModifier":
            touch = _item_touch(
                sde,
                m,
                value,
                items,
                lambda i, g=m.group: sde.group_id(i) == g,
            )
        elif m.func == "ItemModifier" and m.domain == "shipID":
            touch = _hull_touch(sde, m, value, fit, layers)
        elif m.func == "ItemModifier" and m.domain == "charID":
            touch = _pilot_touch(sde, m, value, fit)
        if touch:
            out.append(touch)
    return out


def trait_touches(sde: SdeData, hull: int) -> dict[int, Touch]:
    out = {}
    for skill, bonuses in sde.hull_traits(hull).items():
        bonus, text, _ = bonuses[0]
        out[skill] = Touch(
            trait_bucket(text),
            float(bonus or 0),
            "hull bonus: " + _TAGS_RE.sub("", text),
        )
    return out


# ---------------------------------------------------------------- capability
def classify(sde: SdeData, fit: ParsedFit, roles=()) -> str:
    """One capability per doctrine fitting; roles are its doctrine roles."""
    hull_group = sde.group_name(fit.hull)
    names = [sde.name(m) for m in fit.module_ids]
    groups = [sde.group_name(m).lower() for m in fit.module_ids]
    online_bursts = sum(
        1
        for (tid, online, _) in fit.modules
        if online and _BURST_RE.search(sde.name(tid))
    )
    remote = sum(1 for n in names if _REMOTE_RE.search(n))
    weapons = sum(
        1
        for m in fit.module_ids
        if 64 in sde.attrs(m) or "launcher" in sde.group_name(m).lower()
    )
    ewar = sum(any(w in g for w in EWAR_WORDS) for g in groups)
    tackle = sum(any(w in g for w in TACKLE_WORDS) for g in groups)
    cyno = any("cynosural" in n.lower() for n in names)
    supportish = bool(set(roles) & {"support", "secondary", "utility"})
    if hull_group in ("Dreadnought", "Lancer Dreadnought"):
        return "Dreads"
    if hull_group == "Carrier":
        return "Carriers"
    if (
        hull_group in ("Force Auxiliary", "Logistics", "Logistics Frigate")
        or remote >= 2
    ):
        return "Logistics"
    if online_bursts:
        return "Links"
    if hull_group in (
        "Interdictor",
        "Heavy Interdiction Cruiser",
        "Interceptor",
    ):
        return "Tackle"
    if hull_group in ("Black Ops", "Covert Ops", "Expedition Frigate") or (
        cyno and weapons == 0
    ):
        return "Recon"
    if hull_group in (
        "Combat Recon Ship",
        "Force Recon Ship",
        "Electronic Attack Ship",
    ):
        cloaked = any("cloaking" in g for g in groups)
        return "Recon" if (cyno or cloaked) and not ewar else "Support"
    if ewar >= 2 and supportish:
        return "Support"
    if tackle and supportish and "Battleship" not in hull_group:
        return "Tackle"
    return "DPS"


# ---------------------------------------------------------------- result
@dataclass
class Row:
    skill: int
    name: str
    required_level: int = 0  # from the hull, modules, charges, drones
    fit_level: int = 0  # extra level a baseline pilot needs to fit it (R17)
    core_level: int = 0
    optimal_level: int = 0
    sources: dict = field(default_factory=dict)  # tier -> [source, ...]
    bucket: str = ""
    per_level: float = 0.0
    reason: str = ""
    mastery: str = ""
    empirical_level: int | None = None
    proven_meeting_core: float | None = None
    overridden: bool = False

    @property
    def tier(self) -> str:
        if self.required_level or self.fit_level:
            return "required"
        if self.core_level:
            return "core"
        return "optimal"

    def add_source(self, tier: str, source: str):
        bucket = self.sources.setdefault(tier, [])
        if source not in bucket:
            bucket.append(source)

    @property
    def weight(self) -> float:
        return self.per_level * rules.BUCKET_WEIGHTS.get(
            self.bucket, rules.DEFAULT_BUCKET_WEIGHT
        )


@dataclass
class Requirements:
    capability: str
    tank_layers: list
    rows: dict  # skill -> Row
    alternatives: dict  # preferred module -> [substitute modules]
    alternative_requirements: dict  # module -> {skill: level}
    proven_pilots: int = 0
    proven_pass_rate: float | None = None
    unknown_items: list = field(default_factory=list)

    def required(self) -> dict[int, int]:
        """Item requirements a character must meet (substituted slots excluded)."""
        return {
            s: r.required_level
            for s, r in self.rows.items()
            if r.required_level
        }

    def core(self) -> dict[int, int]:
        return {
            s: max(r.required_level, r.core_level)
            for s, r in self.rows.items()
            if r.required_level or r.core_level
        }


@dataclass
class Override:
    skill: int
    action: str  # pin, exclude, set_level
    tier: str  # required, core, optimal
    level: int = 0
    note: str = ""


def _quantile_level(levels: list[int], q: float) -> int:
    levels = sorted(levels)
    return levels[min(len(levels) - 1, int(q * len(levels)))]


def fit_plan(
    sde: SdeData, fit: ParsedFit, base: dict[int, int]
) -> tuple[dict[int, int], list[str]]:
    """R17: the cheapest extra fitting-skill levels a baseline pilot needs.

    Greedy: raise the level that closes the most CPU / grid / calibration /
    drone shortfall per training day, until the fit fits.
    """
    items = fit.fit_items()
    skills = dict(base)
    result = check_fit(sde, items, skills)
    if result.fits:
        return {}, []
    candidates = sorted(fitting_skill_ids(sde, items))

    def shortfall(r) -> float:
        return (
            r.cpu_short / max(r.cpu_output, 1)
            + r.power_short / max(r.power_output, 1)
            + max(0.0, r.calibration_used - r.calibration_output) / 400
            + max(0.0, r.drones_needed - r.drones_max)
        )

    problems = list(result.problems)
    for _ in range(60):
        current = shortfall(result)
        best, best_value = None, None
        for skill in candidates:
            have = skills.get(skill, 0)
            if have >= 5:
                continue
            trial = dict(skills)
            trial[skill] = have + 1
            for pre, lv in sde.with_prerequisites({skill: have + 1}).items():
                trial[pre] = max(trial.get(pre, 0), lv)
            r = check_fit(sde, items, trial)
            gain = current - shortfall(r)
            if gain <= 1e-9:
                continue
            days = sum(
                train_days(sde, s, skills.get(s, 0), lv)
                for s, lv in trial.items()
                if lv > skills.get(s, 0)
            )
            value = gain / max(days, 0.01)
            if best_value is None or value > best_value:
                best_value, best = value, (trial, r)
        if best is None:
            break
        skills, result = best
        if result.fits:
            break
    extra = {s: lv for s, lv in skills.items() if lv > base.get(s, 0)}
    return extra, ([] if result.fits else problems)


class _Builder:
    """Builds the rows for one fitting; compute() runs the steps in order."""

    def __init__(self, sde: SdeData, fit: ParsedFit, substitutes, proven):
        self.sde = sde
        self.fit = fit
        self.substitutes = {k: v for k, v in (substitutes or {}).items() if v}
        self.substituted = set(self.substitutes) & set(fit.module_ids)
        fixed = [fit.hull] + [
            i for i in fit.items() if i not in self.substituted
        ]
        self.hard = hard_requirements(sde, fixed)
        self.alt_reqs = {
            module: hard_requirements(sde, [module])
            for preferred in self.substituted
            for module in [preferred] + self.substitutes[preferred]
        }
        # Display and fit-plan baseline: the preferred modules' requirements.
        self.display_hard = hard_requirements(sde, [fit.hull] + fit.items())
        self.proven = [p for p in (proven or []) if meets(p, self.hard)]
        self.use_empirical = len(self.proven) >= rules.EMPIRICAL_MIN_PILOTS
        self.rows: dict[int, Row] = {}

    def row(self, skill: int) -> Row:
        if skill not in self.rows:
            self.rows[skill] = Row(skill=skill, name=self.sde.name(skill))
        return self.rows[skill]

    def required(self):
        for s, lv in self.display_hard.items():
            r = self.row(s)
            r.required_level = lv
            r.add_source("required", "hard")

    def candidates(self, layers):
        """R5-R9, R11: masteries, traits and hard skills through the filter."""
        mastery = self.sde.mastery_levels(self.fit.hull)
        traits = trait_touches(self.sde, self.fit.hull)
        for s in set(mastery) | set(self.display_hard) | set(traits):
            t = touches(self.sde, s, self.fit, layers)
            if s in traits:
                t.append(traits[s])
            if not t and s not in self.display_hard:
                continue  # R6: the dogma filter drops it
            self._candidate(s, t, mastery.get(s), s in traits)

    def _core_level(self, s, m, is_trait):
        core = m[rules.CORE_MASTERY_LEVEL - 1] if m else 0
        sources = ["mastery"] if core else []
        if is_trait and rules.TRAIT_CORE_LEVEL > core:
            core, sources = rules.TRAIT_CORE_LEVEL, ["dogma"]
        empirical = None
        if self.use_empirical:
            empirical = _quantile_level(
                [p.get(s, 0) for p in self.proven], rules.EMPIRICAL_QUANTILE
            )
            top = m[rules.OPTIMAL_MASTERY_LEVEL - 1] if m else 0
            raised = min(empirical, 5 if is_trait else max(top, core))
            if raised > core:
                core = raised
                sources.append("empirical")
        return core, sources, empirical

    def _candidate(self, s, t, m, is_trait):
        core, sources, empirical = self._core_level(s, m, is_trait)
        best = max(t, key=lambda x: x.per_level) if t else None
        r = self.row(s)
        r.mastery = "".join(map(str, m)) if m else ""
        r.empirical_level = empirical
        if best is not None:
            r.bucket, r.per_level, r.reason = (
                best.bucket,
                best.per_level,
                best.why,
            )
        if core > r.required_level:
            r.core_level = core
            for src in sources + (["dogma"] if best is not None else []):
                r.add_source("core", src)
        floor = max(r.core_level, r.required_level)
        if m:
            r.optimal_level = max(m[rules.OPTIMAL_MASTERY_LEVEL - 1], floor)
        elif is_trait or (
            best is not None and best.per_level >= rules.OPTIMAL_MIN_BONUS
        ):
            r.optimal_level = 5
        else:
            r.optimal_level = floor
        if r.optimal_level > floor:
            r.add_source("optimal", "mastery" if m else "dogma")

    def capability_buckets(self, capability):
        """R10: core counts only the buckets that matter for this job."""
        core_buckets = rules.CORE_BUCKETS[capability]
        for r in self.rows.values():
            if r.core_level and r.bucket and r.bucket not in core_buckets:
                r.optimal_level = max(r.optimal_level, r.core_level)
                r.add_source("optimal", r.sources.get("core", ["mastery"])[0])
                r.core_level = 0
                r.sources.pop("core", None)

    def kit(self):
        """R2: utility drones are optional."""
        kit = {}
        for tid, _ in self.fit.kit:
            for s, lv in self.sde.required_skills(tid).items():
                kit[s] = max(kit.get(s, 0), lv)
        for s, lv in self.sde.with_prerequisites(kit).items():
            if lv <= self.display_hard.get(s, 0):
                continue
            r = self.row(s)
            if lv > r.optimal_level:
                r.optimal_level = lv
                r.add_source("optimal", "hard")
                r.reason = r.reason or "utility drones"

    def fit_levels(self):
        """R17: what a pilot with only the hard requirements needs to fit it."""
        extra, _ = fit_plan(self.sde, self.fit, self.display_hard)
        for s, lv in extra.items():
            r = self.row(s)
            r.fit_level = lv
            r.add_source("required", "hard")
            r.reason = r.reason or "needed to fit the modules"
            r.optimal_level = max(r.optimal_level, lv)

    def proven_stats(self) -> float | None:
        """R12: share of Proven pilots meeting each core row, and all of them."""
        if not self.use_empirical:
            return None
        n = len(self.proven)
        for r in self.rows.values():
            if r.core_level > r.required_level:
                r.proven_meeting_core = (
                    sum(
                        1
                        for p in self.proven
                        if p.get(r.skill, 0) >= r.core_level
                    )
                    / n
                )
        core_map = {
            s: max(r.required_level, r.core_level)
            for s, r in self.rows.items()
            if r.required_level or r.core_level
        }
        return sum(1 for p in self.proven if meets(p, core_map)) / n

    def relax_substituted(self):
        """Substituted slots are checked per alternative (readiness), so the
        fixed rows keep only what the rest of the fit needs."""
        for preferred in self.substituted:
            for s, lv in self.alt_reqs[preferred].items():
                r = self.rows.get(s)
                if (
                    r
                    and not r.overridden
                    and r.required_level == lv
                    and self.hard.get(s, 0) < lv
                ):
                    r.required_level = self.hard.get(s, 0)
                    r.reason = r.reason or "or a substitute module"


def compute(
    sde: SdeData,
    fit: ParsedFit,
    *,
    roles=(),
    capability_override: str | None = None,
    proven_skills: list[dict[int, int]] | None = None,
    substitutes: dict[int, list[int]] | None = None,
    overrides: list[Override] | None = None,
) -> Requirements:
    """Requirement rows for one fitting.

    proven_skills: skill maps of the characters with PROVEN_MIN_FLEETS+
    fleets in this hull (R9 filters them to hard-ready ones).
    """
    b = _Builder(sde, fit, substitutes, proven_skills)
    layers = tank_layers(sde, fit)
    capability = capability_override or classify(sde, fit, roles)
    b.required()
    b.candidates(layers)
    b.capability_buckets(capability)
    b.kit()
    b.fit_levels()
    _apply_overrides(sde, b.rows, overrides or [])
    pass_rate = b.proven_stats()
    b.relax_substituted()
    return Requirements(
        capability=capability,
        tank_layers=sorted(layers),
        rows={
            s: r
            for s, r in b.rows.items()
            if r.required_level
            or r.fit_level
            or r.core_level
            or r.optimal_level
        },
        alternatives={p: b.substitutes[p] for p in b.substituted},
        alternative_requirements=b.alt_reqs,
        proven_pilots=len(b.proven),
        proven_pass_rate=pass_rate,
        unknown_items=list(fit.unknown),
    )


def _apply_overrides(sde: SdeData, rows: dict, overrides: list[Override]):
    """R13: doctrine-team corrections win."""
    for o in overrides:
        r = rows.get(o.skill)
        if o.action == "exclude":
            if r is not None:
                rows.pop(o.skill)
            continue
        if r is None:
            r = rows[o.skill] = Row(skill=o.skill, name=sde.name(o.skill))
        level = max(0, min(5, int(o.level)))
        if o.tier == "required":
            r.required_level = level
        elif o.tier == "core":
            r.core_level = level
        else:
            r.optimal_level = level
        r.optimal_level = max(r.optimal_level, r.core_level, r.required_level)
        r.sources[o.tier] = ["override"]
        r.overridden = True
        if o.note:
            r.reason = o.note
