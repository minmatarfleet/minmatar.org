"""
EFT → in-game representations. Turns an EFT block into the item list ESI
expects when saving a fitting, and into the DNA string EVE's chat client
opens as a fitting window (``<a href="fitting:DNA">``).
"""

import re
from dataclasses import dataclass

from eveuniverse.models import EveType, EveTypeDogmaEffect

from fleets.helpers.refits import _split_qty, parse_cargo_modules

# EveCategory ids whose items live in a bay rather than the cargohold.
_DRONE_CATEGORY = 18
_FIGHTER_CATEGORY = 87

_SLOT_FLAG_PREFIX = {
    "low": "LoSlot",
    "mid": "MedSlot",
    "high": "HiSlot",
    "rig": "RigSlot",
    "subsystem": "SubSystemSlot",
}
_QTY_SUFFIX_RE = re.compile(r"\s+x\d+$")
# Fit names may themselves contain brackets: ``[Hurricane, Cane [FL33T]]``.
_HEADER_RE = re.compile(r"^\[(?P<ship>[^,\]]+)(?:,\s*(?P<name>.*))?\]$")

# Dogma effect ids that place a module in a slot (stable SDE ids).
_SLOT_EFFECTS = {
    11: "low",
    12: "high",
    13: "mid",
    2663: "rig",
    3772: "subsystem",
}


def eft_item_names(eft_format: str) -> set[str]:
    """Every module/item name in an EFT block (charges and quantities stripped)."""
    names: set[str] = set()
    for raw in (eft_format or "").splitlines()[1:]:
        line = raw.strip()
        if not line or line.startswith("[Empty "):
            continue
        line = _QTY_SUFFIX_RE.sub("", line)
        names.add(line.split(",", 1)[0].strip())
    names.discard("")
    return names


def module_slots_for(names: set[str]) -> dict[str, str]:
    """name -> slot for the given item names, from the universe dogma cache."""
    if not names:
        return {}
    id_to_name = dict(
        EveType.objects.filter(name__in=names).values_list("id", "name")
    )
    if not id_to_name:
        return {}
    slots: dict[str, str] = {}
    for row in EveTypeDogmaEffect.objects.filter(
        eve_type_id__in=id_to_name.keys(),
        eve_dogma_effect_id__in=_SLOT_EFFECTS.keys(),
    ).values("eve_type_id", "eve_dogma_effect_id"):
        name = id_to_name[row["eve_type_id"]]
        slot = _SLOT_EFFECTS[row["eve_dogma_effect_id"]]
        if slot == "rig" or name not in slots:
            slots[name] = slot
    return slots


@dataclass
class EftItem:
    """One line of an EFT block below the header."""

    name: str
    quantity: int = 1
    charge: str | None = None
    stacked: bool = False  # ``Name xN`` line: drones or cargo, never a slot


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
        if _QTY_SUFFIX_RE.search(line):
            name, qty = _split_qty(line)
            items.append(EftItem(name=name, quantity=qty, stacked=True))
            continue
        name, _, charge = line.partition(",")
        items.append(EftItem(name=name.strip(), charge=charge.strip() or None))
    return items


def _resolve_types(names: set[str]) -> dict[str, tuple[int, int | None]]:
    """name -> (type_id, category_id) for every known name."""
    if not names:
        return {}
    rows = EveType.objects.filter(name__in=names).values_list(
        "name", "id", "eve_group__eve_category_id"
    )
    return {name: (type_id, category) for name, type_id, category in rows}


def _bay_flag(category_id: int | None) -> str:
    if category_id == _DRONE_CATEGORY:
        return "DroneBay"
    if category_id == _FIGHTER_CATEGORY:
        return "FighterBay"
    return "Cargo"


def eft_to_esi_fitting(eft_format: str) -> tuple[int | None, list[dict]]:
    """
    (ship_type_id, items) for ESI ``POST /characters/{id}/fittings``.
    Modules take the next free slot of their kind, charges share the module's
    slot, ``Name xN`` lines go to the drone/fighter bay or cargo. Unknown
    names (not in the universe cache) are dropped rather than guessed.
    """
    ship_name, _ = parse_eft_header(eft_format)
    parsed = parse_eft_items(eft_format)
    names = {item.name for item in parsed} | {
        item.charge for item in parsed if item.charge
    }
    if ship_name:
        names.add(ship_name)
    types = _resolve_types(names)
    ship = types.get(ship_name)
    if not ship:
        return None, []
    slots = module_slots_for(
        {item.name for item in parsed if not item.stacked}
    )

    next_index: dict[str, int] = {}
    items: list[dict] = []
    for item in parsed:
        known = types.get(item.name)
        if not known:
            continue
        type_id, category = known
        if item.stacked:
            items.append(
                {
                    "type_id": type_id,
                    "flag": _bay_flag(category),
                    "quantity": item.quantity,
                }
            )
            continue
        slot = slots.get(item.name)
        prefix = _SLOT_FLAG_PREFIX.get(slot or "")
        if not prefix:
            items.append({"type_id": type_id, "flag": "Cargo", "quantity": 1})
            continue
        index = next_index.get(slot, 0)
        next_index[slot] = index + 1
        flag = f"{prefix}{index}"
        items.append({"type_id": type_id, "flag": flag, "quantity": 1})
        charge = types.get(item.charge) if item.charge else None
        if charge:
            items.append({"type_id": charge[0], "flag": flag, "quantity": 1})
    return ship[0], items


def eft_to_dna(eft_format: str) -> str | None:
    """
    DNA string for an in-game ``fitting:`` link. Fitted modules and charges
    are listed as ``type;qty``; bay and cargo items as ``type_;qty``.
    None when the hull is unknown.
    """
    ship_id, items = eft_to_esi_fitting(eft_format)
    if not ship_id:
        return None
    fitted: dict[int, int] = {}
    fitted_order: list[int] = []
    cargo: dict[int, int] = {}
    cargo_order: list[int] = []
    for item in items:
        target, order = (
            (cargo, cargo_order)
            if item["flag"] in ("Cargo", "DroneBay", "FighterBay")
            else (fitted, fitted_order)
        )
        if item["type_id"] not in target:
            order.append(item["type_id"])
        target[item["type_id"]] = (
            target.get(item["type_id"], 0) + item["quantity"]
        )
    parts = [str(ship_id)]
    parts.extend(f"{tid};{fitted[tid]}" for tid in fitted_order)
    parts.extend(f"{tid}_;{cargo[tid]}" for tid in cargo_order)
    return ":".join(parts) + "::"


def fitting_href(eft_format: str) -> str | None:
    """``fitting:DNA`` href for MOTD links, or None when it cannot be built."""
    dna = eft_to_dna(eft_format)
    return f"fitting:{dna}" if dna else None


_SWAPPABLE_SLOTS = ("low", "mid", "high")


def _validate_swaps(base_eft: str, swaps: list[tuple[str, str]]) -> str | None:
    """
    A swap must pull a module the cargohold actually carries (no more times
    than it is carried) into a slot of the same kind. Returns an error or
    None. Slot kinds come from the universe cache; unknown modules pass.
    """
    stock = {
        item.name: item.quantity
        for item in parse_eft_items(base_eft)
        if item.stacked
    }
    used: dict[str, int] = {}
    for _, module_in in swaps:
        used[module_in] = used.get(module_in, 0) + 1
        if used[module_in] > stock.get(module_in, 0):
            return f"Only {stock.get(module_in, 0)} x {module_in} in the cargohold"

    names = {name for pair in swaps for name in pair}
    slots = module_slots_for(names)
    for module_out, module_in in swaps:
        out_slot, in_slot = slots.get(module_out), slots.get(module_in)
        if out_slot and out_slot not in _SWAPPABLE_SLOTS:
            return f"{module_out} is not in a swappable slot"
        if out_slot and in_slot and out_slot != in_slot:
            return f"{module_in} does not fit a {out_slot} slot ({module_out})"
    return None


def refit_eft_from_swaps(
    base_eft: str, swaps: list[tuple[str, str]], refit_name: str
) -> tuple[str, str | None]:
    """
    Apply slot swaps (module_out -> module_in) to the base EFT: each swapped
    module line is replaced, the module taken from cargo is decremented and
    the removed module is added to cargo. Returns (eft, error).
    """
    lines = (base_eft or "").strip().splitlines()
    if not lines:
        return "", "Base fit is empty"
    ship_name, _ = parse_eft_header(base_eft)
    if not ship_name:
        return "", "Base fit has no EFT header"

    error = _validate_swaps(base_eft, swaps)
    if error:
        return "", error

    body = lines[1:]
    replaced: set[int] = set()
    cargo_delta: dict[str, int] = {}
    for module_out, module_in in swaps:
        found = None
        for index, raw in enumerate(body):
            line = raw.strip()
            if (
                not line
                or line.startswith("[Empty ")
                or _QTY_SUFFIX_RE.search(line)
                or index in replaced
            ):
                continue
            if line.split(",", 1)[0].strip() == module_out:
                found = index
                break
        if found is None:
            return "", f"{module_out} is not fitted on the base fit"
        body[found] = module_in
        replaced.add(found)
        cargo_delta[module_in] = cargo_delta.get(module_in, 0) - 1
        cargo_delta[module_out] = cargo_delta.get(module_out, 0) + 1

    # Rewrite stacked lines with the cargo changes applied.
    stacked_indexes = [
        i for i, raw in enumerate(body) if _QTY_SUFFIX_RE.search(raw.strip())
    ]
    stacked = parse_cargo_modules(
        "\n".join(body[i].strip() for i in stacked_indexes)
    )
    counts = dict(stacked)
    order = [name for name, _ in stacked]
    for name, delta in cargo_delta.items():
        if name not in counts:
            order.append(name)
        counts[name] = counts.get(name, 0) + delta
    kept = [f"{name} x{counts[name]}" for name in order if counts[name] > 0]

    stacked_set = set(stacked_indexes)
    fitted = [raw for i, raw in enumerate(body) if i not in stacked_set]
    while fitted and not fitted[-1].strip():
        fitted.pop()
    header = f"[{ship_name}, {refit_name}]"
    out = [header, *fitted]
    if kept:
        out.append("")
        out.extend(kept)
    return "\n".join(out) + "\n", None
