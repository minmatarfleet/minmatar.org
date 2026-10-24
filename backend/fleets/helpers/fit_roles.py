"""
Fleet roles a fit fills, read from its EFT.

Roles are no longer signed up for separately: a pilot who brings a links
ship runs links, a cyno fit lights cynos, a logi fit repairs. The FC still
names a Logi FC by hand, because that is a person, not a ship.

Links come from command burst modules. EFT marks the ones the doctrine
runs online; the rest are fitted ``/offline`` so a pilot can swap which
bursts they run. Spares in cargo are not counted: swapping those in needs a
depot. Calibrated against every production doctrine fit (Oct 2026).
"""

import re
from collections import Counter
from dataclasses import dataclass, field

from fittings.eft import parse_eft_items

# Display order; also the canonical order of a stored burst list.
BURST_KINDS = ("armor", "shield", "skirmish", "information", "mining")
BURST_LABELS = {
    "armor": "Armor",
    "shield": "Shield",
    "skirmish": "Skirmish",
    "information": "Information",
    "mining": "Mining",
}

_BURST_RE = re.compile(
    r"^(?P<kind>Armor|Shield|Skirmish|Information) Command Burst\b"
    r"|^(?P<mining>Mining Foreman) Burst\b"
)
# Remote armor/shield/hull reps and cap transfers, any size or variant:
# "Medium Remote Armor Repairer II", "Capital I-ax Enduring Remote Armor
# Repairer", "Large Inductive Compact Remote Capacitor Transmitter".
_REMOTE_RE = re.compile(
    r"\bRemote (Armor Repairer|Shield Booster|Hull Repairer|"
    r"Capacitor Transmitter)\b"
)
# Covert and industrial variants included.
_CYNO_RE = re.compile(r"\bCynosural Field Generator\b")

# A fit with one remote rep is a brawler buddy-repping (Pointrunner
# Myrmidon), not logi. Logi hulls count even with one big module (Zarmazd).
LOGI_MIN_REMOTE_MODULES = 2
LOGI_HULL_GROUPS = frozenset(
    {"Logistics", "Logistics Frigate", "Force Auxiliary"}
)


def burst_kind(module_name: str) -> str | None:
    match = _BURST_RE.match(module_name or "")
    if not match:
        return None
    if match.group("mining"):
        return "mining"
    return match.group("kind").lower()


@dataclass(frozen=True)
class FitRoles:
    bursts_fitted: dict = field(default_factory=dict)  # kind -> count
    bursts_online: dict = field(default_factory=dict)  # kind -> count
    cyno: bool = False
    logi: bool = False

    @property
    def burst_slots(self) -> int:
        """How many bursts the fit can run at once."""
        return sum(self.bursts_online.values())

    @property
    def links(self) -> bool:
        return self.burst_slots > 0

    def default_bursts(self) -> list[str]:
        """The doctrine's online bursts, in canonical order."""
        return [
            kind
            for kind in BURST_KINDS
            for _ in range(self.bursts_online.get(kind, 0))
        ]

    def validate_bursts(self, bursts: list[str]) -> str | None:
        """None when a pilot's burst pick is runnable on this fit."""
        if not self.links:
            return "This fit has no command bursts" if bursts else None
        if len(bursts) > self.burst_slots:
            return (
                f"This fit runs {self.burst_slots} bursts at once; "
                f"{len(bursts)} were picked"
            )
        for kind, count in Counter(bursts).items():
            fitted = self.bursts_fitted.get(kind, 0)
            if count > fitted:
                label = BURST_LABELS.get(kind, kind)
                return (
                    f"Only {fitted} {label} burst"
                    f"{'' if fitted == 1 else 's'} fitted"
                )
        return None


def canonical_bursts(bursts: list[str]) -> list[str]:
    order = {kind: index for index, kind in enumerate(BURST_KINDS)}
    return sorted(bursts, key=lambda kind: order.get(kind, len(order)))


def fit_roles(eft_format: str, ship_group: str = "") -> FitRoles:
    fitted: Counter = Counter()
    online: Counter = Counter()
    remote = 0
    cyno = False
    for item in parse_eft_items(eft_format):
        if item.stacked:
            continue  # drones and cargo
        kind = burst_kind(item.name)
        if kind:
            fitted[kind] += 1
            if not item.offline:
                online[kind] += 1
        elif _REMOTE_RE.search(item.name):
            remote += 1
        elif _CYNO_RE.search(item.name):
            cyno = True
    return FitRoles(
        bursts_fitted=dict(fitted),
        bursts_online=dict(online),
        cyno=cyno,
        logi=remote >= LOGI_MIN_REMOTE_MODULES
        or (remote > 0 and ship_group in LOGI_HULL_GROUPS),
    )
