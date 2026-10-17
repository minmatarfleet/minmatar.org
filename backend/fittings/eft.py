"""
The backend's one EFT parser.

EFT is the text format EVE and pyfa use to copy a fit::

    [Hurricane, Hurricane [FL33T]]
    Gyrostabilizer II
    [Empty Low slot]
    Heavy Missile Launcher II, Scourge Heavy Missile
    Stasis Webifier II /offline

    Hammerhead II x5
    Scourge Heavy Missile x2000

The first line is ``[Ship, Fit name]`` (the fit name may contain brackets).
Below it, each fitted module is one line, optionally with a loaded charge
after a comma and a trailing ``/offline``. ``Name xN`` lines are drones or
cargo. ``[Empty ...]`` lines are empty slots.

``parse_eft_header`` and ``parse_eft_items`` are the parser; the other
functions are projections for what each caller needs. Pure text: no model
imports, so any app can use it.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

# Dogma effect ids that place a module in a slot (stable SDE ids).
EFFECT_LO_POWER = 11
EFFECT_HI_POWER = 12
EFFECT_MED_POWER = 13
EFFECT_RIG_SLOT = 2663
EFFECT_SUBSYSTEM = 3772

SLOT_EFFECTS = {
    EFFECT_LO_POWER: "low",
    EFFECT_HI_POWER: "high",
    EFFECT_MED_POWER: "mid",
    EFFECT_RIG_SLOT: "rig",
    EFFECT_SUBSYSTEM: "subsystem",
}

_QTY_SUFFIX_RE = re.compile(r"^(?P<name>.+?)\s+x(?P<qty>\d+)$")
_QTY_PREFIX_RE = re.compile(r"^(?P<qty>\d+)\s*x\s+(?P<name>.+)$")
# EFT marks a fitted-but-offline module with a trailing ``/offline``. In-game
# fittings do not store online state, so the module itself still counts.
_OFFLINE_SUFFIX_RE = re.compile(r"\s*/offline$", re.IGNORECASE)
# Fit names may themselves contain brackets: ``[Hurricane, Cane [FL33T]]``.
_HEADER_RE = re.compile(r"^\[(?P<ship>[^,\]]+)(?:,\s*(?P<name>.*))?\]$")


def split_qty(line: str) -> tuple[str, int]:
    """``Name x3`` / ``3x Name`` -> (Name, 3); plain line -> (line, 1)."""
    m = _QTY_SUFFIX_RE.match(line)
    if m:
        return m.group("name").strip(), int(m.group("qty"))
    m = _QTY_PREFIX_RE.match(line)
    if m:
        return m.group("name").strip(), int(m.group("qty"))
    return line, 1


def is_stacked_line(line: str) -> bool:
    """True for a ``Name xN`` line (drones or cargo, never a slot)."""
    return bool(_QTY_SUFFIX_RE.match(line.strip()))


@dataclass
class EftItem:
    """One line of an EFT block below the header."""

    name: str
    quantity: int = 1
    charge: str | None = None
    stacked: bool = False  # ``Name xN`` line: drones or cargo, never a slot
    offline: bool = False  # fitted with a trailing ``/offline``


def parse_eft_header(eft_format: str) -> tuple[str, str]:
    """``[Hurricane, Hurricane [FL33T]]`` -> ("Hurricane", "Hurricane [FL33T]")."""
    lines = (eft_format or "").strip().splitlines()
    if not lines:
        return "", ""
    m = _HEADER_RE.match(lines[0].strip())
    if not m:
        return "", ""
    return m.group("ship").strip(), (m.group("name") or "").strip()


def parse_eft_items(eft_format: str) -> list[EftItem]:
    """Every fitted module, drone and cargo line (empty slots skipped)."""
    items: list[EftItem] = []
    for raw in (eft_format or "").strip().splitlines()[1:]:
        line = raw.strip()
        if not line or line.startswith("[Empty "):
            continue
        if _QTY_SUFFIX_RE.match(line):
            name, qty = split_qty(line)
            items.append(EftItem(name=name, quantity=qty, stacked=True))
            continue
        offline = bool(_OFFLINE_SUFFIX_RE.search(line))
        line = _OFFLINE_SUFFIX_RE.sub("", line)
        name, _, charge = line.partition(",")
        if not name.strip():
            continue
        items.append(
            EftItem(
                name=name.strip(),
                charge=charge.strip() or None,
                offline=offline,
            )
        )
    return items


def eft_item_names(eft_format: str) -> set[str]:
    """Every module/drone/cargo name below the header (no charges, no hull)."""
    return {item.name for item in parse_eft_items(eft_format)}


def fitted_modules(eft_format: str) -> Counter:
    """
    Modules fitted in slots, counted per line. Drones/cargo (``Name xN``),
    empty slots, loaded charges and ``/offline`` markers are left out, so
    ``Launcher II, Scourge`` counts as one ``Launcher II``.
    """
    return Counter(
        item.name for item in parse_eft_items(eft_format) if not item.stacked
    )


def purchase_items(eft_format: str) -> Counter:
    """
    What to buy for one copy of a fit: the hull plus every fitted module and
    rig. Charges, drones and cargo are left out, so a fit still counts as
    available when only ammo is missing.
    """
    needed: Counter = Counter()
    ship, _ = parse_eft_header(eft_format)
    if ship:
        needed[ship] += 1
    needed.update(fitted_modules(eft_format))
    return needed


def item_quantities(eft_format: str) -> dict[str, int]:
    """
    ``{name: quantity}`` for the whole fit: the hull (1), each fitted module
    (1 per line), each loaded charge (1 per module line it is loaded in, the
    same way an in-game fitting stores it) and every ``Name xN`` line.
    """
    items: Counter = Counter()
    ship, _ = parse_eft_header(eft_format)
    if ship:
        items[ship] += 1
    for item in parse_eft_items(eft_format):
        items[item.name] += item.quantity
        if item.charge:
            items[item.charge] += 1
    return dict(items)
