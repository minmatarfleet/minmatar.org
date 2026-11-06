"""Recruitment rule kinds: what each one's params look like and how it reads.

A rule is (kind, params, who, importance). ``clean_rule`` validates what a
CEO submits; ``describe`` turns a stored rule into the sentence applicants
and recruiters see. New kinds are added here and in ``evaluate``.
"""

from dataclasses import dataclass

from applications.models import CorporationRequirement as Rule
from capabilities.engine.rules import CAPABILITIES
from fittings.models import EveDoctrine
from timezones.brackets import BRACKET_CODES

LEVEL_CAN_FLY = "can_fly"
LEVEL_DOCTRINE_READY = "doctrine_ready"
LEVEL_FLOWN = "flown"
SHIP_LEVELS = (LEVEL_CAN_FLY, LEVEL_DOCTRINE_READY, LEVEL_FLOWN)

TARGET_DOCTRINE = "doctrine"
TARGET_CAPABILITY = "capability"

# How a capability reads in a sentence ("Fly a Dreadnought").
CAPABILITY_PHRASES = {
    "DPS": "a DPS ship",
    "Logistics": "Logistics",
    "Links": "command links",
    "Support": "a support ship",
    "Tackle": "tackle",
    "Recon": "a recon ship",
    "Dreads": "a Dreadnought",
    "Carriers": "a Carrier",
}
CAPABILITY_LABELS = {
    "DPS": "DPS",
    "Logistics": "Logistics",
    "Links": "Command links",
    "Support": "Support",
    "Tackle": "Tackle",
    "Recon": "Recon",
    "Dreads": "Dreadnought",
    "Carriers": "Carrier",
}

# Kinds that read the person, not one character: ``who`` is always "any".
PERSON_KINDS = frozenset({Rule.KIND_PRIME_TIME})
# Kinds where "an alt on another account" makes no sense.
NO_OTHER_ACCOUNT_KINDS = frozenset({Rule.KIND_KILLS, Rule.KIND_PRIME_TIME})

MAX_RULES_PER_CORPORATION = 12


class RuleError(ValueError):
    """A submitted rule that can't be stored; the message is shown as is."""


@dataclass(frozen=True)
class CleanRule:
    kind: str
    params: dict
    who: str
    importance: str


def _int(params: dict, key: str, low: int, high: int) -> int:
    try:
        value = int(params.get(key))
    except (TypeError, ValueError):
        raise RuleError(f"{key} must be a number") from None
    if value < low or value > high:
        raise RuleError(f"{key} must be between {low} and {high}")
    return value


def _clean_ships(params: dict) -> dict:
    target = params.get("target")
    level = params.get("level") or LEVEL_CAN_FLY
    if level not in SHIP_LEVELS:
        raise RuleError("Unknown level")
    if target == TARGET_CAPABILITY:
        capability = params.get("capability")
        if capability not in CAPABILITIES:
            raise RuleError("Unknown role")
        return {"target": target, "capability": capability, "level": level}
    if target == TARGET_DOCTRINE:
        if level == LEVEL_FLOWN:
            raise RuleError("Has flown it applies to roles, not doctrines")
        doctrine_id = _int(params, "doctrine_id", 1, 2**31 - 1)
        if not EveDoctrine.objects.filter(pk=doctrine_id).exists():
            raise RuleError("Unknown doctrine")
        return {"target": target, "doctrine_id": doctrine_id, "level": level}
    raise RuleError("Pick a doctrine or a role")


def _clean_params(kind: str, params: dict) -> dict:
    params = params or {}
    if kind == Rule.KIND_SHIPS:
        return _clean_ships(params)
    if kind == Rule.KIND_KILLS:
        months = _int(params, "months", 1, 12)
        active = _int(params, "active_months", 1, months)
        return {"months": months, "active_months": active}
    if kind == Rule.KIND_SKILL_POINTS:
        return {"minimum": _int(params, "minimum", 1_000_000, 500_000_000)}
    if kind == Rule.KIND_CHARACTER_AGE:
        return {"months": _int(params, "months", 1, 240)}
    if kind == Rule.KIND_PRIME_TIME:
        brackets = [
            b for b in params.get("brackets") or [] if b in BRACKET_CODES
        ]
        if not brackets:
            raise RuleError("Pick at least one timezone")
        return {"brackets": sorted(set(brackets), key=BRACKET_CODES.index)}
    raise RuleError("Unknown requirement type")


def clean_rule(
    kind: str, params: dict, who: str, importance: str
) -> CleanRule:
    if who not in dict(Rule.WHO_CHOICES):
        raise RuleError("Unknown character choice")
    if importance not in dict(Rule.IMPORTANCE_CHOICES):
        raise RuleError("Unknown importance")
    cleaned = _clean_params(kind, params)
    if kind in PERSON_KINDS:
        who = Rule.WHO_ANY
    elif kind in NO_OTHER_ACCOUNT_KINDS and who == Rule.WHO_OTHER_ACCOUNT:
        raise RuleError("Pick your main or any character for this one")
    return CleanRule(kind, cleaned, who, importance)


def format_sp(value: int) -> str:
    millions = value / 1_000_000
    return f"{millions:g}M"


def _age(months: int) -> str:
    if months % 12 == 0:
        years = months // 12
        return "1 year" if years == 1 else f"{years} years"
    return "1 month" if months == 1 else f"{months} months"


def _ship_object(params: dict, doctrine_names: dict[int, str]) -> str:
    if params.get("target") == TARGET_CAPABILITY:
        return CAPABILITY_PHRASES.get(params.get("capability"), "that role")
    name = doctrine_names.get(params.get("doctrine_id"))
    return f"our {name} doctrine" if name else "a doctrine ship"


def _ships_text(rule, doctrine_names) -> str:
    thing = _ship_object(rule.params, doctrine_names)
    level = rule.params.get("level", LEVEL_CAN_FLY)
    if level == LEVEL_FLOWN:
        verb = f"has flown {thing} in alliance fleets"
        bare = f"Have flown {thing} in alliance fleets"
    elif level == LEVEL_DOCTRINE_READY:
        verb = f"is doctrine-ready in {thing}"
        bare = f"Be doctrine-ready in {thing}"
    else:
        verb = f"can fly {thing}"
        bare = f"Fly {thing}"
    if rule.who == Rule.WHO_MAIN:
        return f"Your main {verb}"
    if rule.who == Rule.WHO_OTHER_ACCOUNT:
        return f"An alt on another account that {verb}"
    return bare


def describe(rule, doctrine_names: dict[int, str] | None = None) -> str:
    """The sentence applicants see for one rule."""
    params = rule.params or {}
    if rule.kind == Rule.KIND_SHIPS:
        return _ships_text(rule, doctrine_names or {})
    if rule.kind == Rule.KIND_KILLS:
        text = (
            f"Kills in {params.get('active_months')} of the last "
            f"{params.get('months')} months"
        )
        return f"{text} on your main" if rule.who == Rule.WHO_MAIN else text
    if rule.kind == Rule.KIND_SKILL_POINTS:
        amount = format_sp(params.get("minimum", 0))
        if rule.who == Rule.WHO_MAIN:
            return f"{amount}+ skill points on your main"
        if rule.who == Rule.WHO_OTHER_ACCOUNT:
            return f"An alt on another account with {amount}+ skill points"
        return f"A character with {amount}+ skill points"
    if rule.kind == Rule.KIND_CHARACTER_AGE:
        age = _age(params.get("months", 0))
        if rule.who == Rule.WHO_MAIN:
            return f"Your main is at least {age} old"
        if rule.who == Rule.WHO_OTHER_ACCOUNT:
            return f"An alt on another account at least {age} old"
        return f"A character at least {age} old"
    if rule.kind == Rule.KIND_PRIME_TIME:
        brackets = params.get("brackets") or []
        if len(brackets) > 1:
            joined = ", ".join(brackets[:-1]) + f" or {brackets[-1]}"
        else:
            joined = brackets[0] if brackets else "our timezone"
        return f"Plays in {joined}"
    return "Unknown requirement"


def doctrine_names_for(rules) -> dict[int, str]:
    ids = {
        rule.params.get("doctrine_id")
        for rule in rules
        if rule.kind == Rule.KIND_SHIPS
        and (rule.params or {}).get("target") == TARGET_DOCTRINE
    }
    ids.discard(None)
    if not ids:
        return {}
    return dict(
        EveDoctrine.objects.filter(pk__in=ids).values_list("id", "name")
    )


def rule_options() -> dict:
    """What the editor offers: doctrines, roles and timezone brackets."""
    doctrines = [
        {"id": doctrine_id, "name": name}
        for doctrine_id, name in EveDoctrine.objects.order_by(
            "name"
        ).values_list("id", "name")
    ]
    return {
        "doctrines": doctrines,
        "capabilities": [
            {"key": key, "label": CAPABILITY_LABELS.get(key, key)}
            for key in CAPABILITIES
        ],
        "brackets": list(BRACKET_CODES),
    }
