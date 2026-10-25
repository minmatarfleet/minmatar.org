"""Turn a doctrine EFT into the typed items the engine reasons about."""

from __future__ import annotations

from dataclasses import dataclass, field

from capabilities.engine.dogma import FitItems
from capabilities.engine.sde import (
    CAT_CHARGE,
    CAT_DRONE,
    CAT_FIGHTER,
    CAT_IMPLANT,
    SdeData,
)
from fittings.eft import parse_eft_header, parse_eft_items

CHARGE_GROUP_ATTRS = (604, 605, 606, 609, 610)
ATTR_CHARGE_SIZE = 128

# A drone boat needs its combat drones; repair, mining and EWAR drones are kit.
COMBAT_DRONE_GROUPS = frozenset(
    {"Combat Drone", "Light Fighter", "Heavy Fighter", "Support Fighter"}
)


@dataclass
class ParsedFit:
    hull: int | None
    modules: list = field(default_factory=list)  # [(type_id, online, charge)]
    charges: list = field(default_factory=list)  # loaded + loadable cargo ammo
    drones: list = field(default_factory=list)  # [(type_id, qty)] required
    kit: list = field(default_factory=list)  # [(type_id, qty)] optional drones
    implants: list = field(default_factory=list)
    unknown: list = field(default_factory=list)
    eft: str = ""

    @property
    def module_ids(self) -> list[int]:
        return [m[0] for m in self.modules]

    def items(self) -> list[int]:
        """Everything whose skills the fit needs (not kit, not implants)."""
        return self.module_ids + self.charges + [d for d, _ in self.drones]

    def fit_items(self, substitutes: dict[int, int] | None = None) -> FitItems:
        subs = substitutes or {}
        return FitItems(
            hull=self.hull,
            modules=[
                (subs.get(t, t), online, c) for t, online, c in self.modules
            ],
            drones=list(self.drones),
            implants=list(self.implants),
        )


def can_load(sde: SdeData, module: int, charge: int) -> bool:
    ma, ca = sde.attrs(module), sde.attrs(charge)
    groups = {int(ma[a]) for a in CHARGE_GROUP_ATTRS if a in ma}
    if sde.group_id(charge) not in groups:
        return False
    if ATTR_CHARGE_SIZE in ma and ATTR_CHARGE_SIZE in ca:
        return ma[ATTR_CHARGE_SIZE] == ca[ATTR_CHARGE_SIZE]
    return True


def is_drone_hull(sde: SdeData, hull: int) -> bool:
    """Hull traits bonus drones or fighters (not just logistic/mining drones)."""
    for bonuses in sde.hull_traits(hull).values():
        for _, text, _ in bonuses:
            t = text.lower()
            if ("drone" in t or "fighter" in t) and not any(
                w in t
                for w in ("logistic drone", "mining drone", "salvage drone")
            ):
                return True
    return False


def parse_fit(sde: SdeData, eft: str, minimum_pod: str = "") -> ParsedFit:
    ship_name, _ = parse_eft_header(eft)
    fit = ParsedFit(
        hull=sde.resolve(ship_name) if ship_name else None, eft=eft
    )
    cargo: list[int] = []
    drones: list[tuple[int, int]] = []
    for item in parse_eft_items(eft):
        tid = sde.resolve(item.name)
        if tid is None:
            fit.unknown.append(item.name)
            continue
        if item.stacked:
            if sde.category(tid) in (CAT_DRONE, CAT_FIGHTER):
                drones.append((tid, item.quantity))
            else:
                cargo.append(tid)
            continue
        charge = sde.resolve(item.charge) if item.charge else None
        if item.charge and charge is None:
            fit.unknown.append(item.charge)
        fit.modules.append((tid, not item.offline, charge))
        if charge:
            fit.charges.append(charge)
    for tid in cargo:
        if sde.category(tid) == CAT_CHARGE and any(
            can_load(sde, m, tid) for m in fit.module_ids
        ):
            if tid not in fit.charges:
                fit.charges.append(tid)
    if fit.hull and is_drone_hull(sde, fit.hull):
        fit.drones = [
            d for d in drones if sde.group_name(d[0]) in COMBAT_DRONE_GROUPS
        ]
        fit.kit = [
            d
            for d in drones
            if sde.group_name(d[0]) not in COMBAT_DRONE_GROUPS
        ]
    else:
        fit.kit = drones
    for line in (minimum_pod or "").splitlines():
        tid = sde.resolve(line) if line.strip() else None
        if tid and sde.category(tid) == CAT_IMPLANT:
            fit.implants.append(tid)
    return fit
