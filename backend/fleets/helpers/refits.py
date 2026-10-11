"""
Fleet refit helpers: EFT module parsing, base-vs-refit cargo diffs, and
validation of which fittings/refits an FC may configure for a fleet.
"""

import re
from collections import Counter

from eveuniverse.models import EveType
from fittings.models import EveFittingRefit

_QTY_SUFFIX_RE = re.compile(r"^(?P<name>.+?)\s+x(?P<qty>\d+)$")
_QTY_PREFIX_RE = re.compile(r"^(?P<qty>\d+)\s*x\s+(?P<name>.+)$")


def _split_qty(line: str) -> tuple[str, int]:
    """``Name x3`` / ``3x Name`` -> (Name, 3); plain line -> (line, 1)."""
    m = _QTY_SUFFIX_RE.match(line)
    if m:
        return m.group("name").strip(), int(m.group("qty"))
    m = _QTY_PREFIX_RE.match(line)
    if m:
        return m.group("name").strip(), int(m.group("qty"))
    return line, 1


def eft_fitted_modules(eft_format: str) -> Counter:
    """
    Count the modules fitted in an EFT block (header, empty slots, blank
    lines and drones/cargo sections are skipped; charges after a comma are
    dropped so ``Launcher II, Scourge`` counts as ``Launcher II``).
    """
    counts: Counter = Counter()
    lines = (eft_format or "").strip().splitlines()
    if not lines:
        return counts
    # Sections after the first blank-line-separated block following the
    # rigs are drones / cargo; EFT has no explicit markers, so treat any
    # ``Name xN`` line as cargo/drones and exclude it from fitted modules.
    for raw in lines[1:]:
        line = raw.strip()
        if not line or line.startswith("[Empty "):
            continue
        if _QTY_SUFFIX_RE.match(line):
            continue
        module = line.split(",", 1)[0].strip()
        if module:
            counts[module] += 1
    return counts


def refit_cargo_diff(base_eft: str, refit_eft: str) -> list[tuple[str, int]]:
    """
    Modules present in the refit but not in the base fit, i.e. what a pilot
    flying the base fit must carry in cargo to refit. Sorted by name.
    """
    base = eft_fitted_modules(base_eft)
    refit = eft_fitted_modules(refit_eft)
    diff = refit - base
    return sorted(diff.items(), key=lambda item: item[0].lower())


def parse_cargo_modules(text: str) -> list[tuple[str, int]]:
    """Parse the FC-editable cargo list (one module per line, ``Name xN``)."""
    modules: Counter = Counter()
    order: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip().lstrip("-•").strip()
        if not line:
            continue
        name, qty = _split_qty(line)
        if name not in modules:
            order.append(name)
        modules[name] += qty
    return [(name, modules[name]) for name in order]


def format_cargo_modules(modules: list[tuple[str, int]]) -> str:
    """Inverse of parse_cargo_modules: ``Name xN`` per line."""
    return "\n".join(f"{name} x{qty}" for name, qty in modules)


def resolve_module_type_ids(names: list[str]) -> dict[str, int]:
    """Best-effort ``name -> type_id`` lookup for MOTD showinfo links."""
    if not names:
        return {}
    return dict(
        EveType.objects.filter(name__in=names).values_list("name", "id")
    )


def default_refit_label(fitting, refit) -> str:
    """
    Short label for a curated refit. Refit names derive from their EFT
    header (e.g. ``Hurricane [FL33T] Cap-stable``); drop the base fitting
    name prefix so the MOTD reads ``Hurricane [FL33T] → Cap-stable``.
    """
    name = (refit.name or "").strip()
    base = (fitting.name or "").strip()
    if base and name.lower().startswith(base.lower()):
        stripped = name[len(base) :].strip(" -–—:")
        if stripped:
            return stripped
    return name


def resolve_fitting_refit(fitting, refit_id: int):
    """Return (refit, error_detail); the refit must belong to the fitting."""
    refit = EveFittingRefit.objects.filter(
        id=refit_id, base_fitting=fitting
    ).first()
    if not refit:
        return None, "Refit not found for this fitting"
    return refit, None
