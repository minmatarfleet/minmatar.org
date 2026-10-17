"""
Fleet refit helpers: EFT module parsing, base-vs-refit cargo diffs, and
validation of which fittings/refits an FC may configure for a fleet.
"""

from collections import Counter

from eveuniverse.models import EveType
from fittings.eft import fitted_modules, split_qty
from fittings.models import EveFittingRefit


def refit_cargo_diff(base_eft: str, refit_eft: str) -> list[tuple[str, int]]:
    """
    Modules present in the refit but not in the base fit, i.e. what a pilot
    flying the base fit must carry in cargo to refit. Sorted by name.
    """
    base = fitted_modules(base_eft)
    refit = fitted_modules(refit_eft)
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
        name, qty = split_qty(line)
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
