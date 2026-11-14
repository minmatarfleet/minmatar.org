"""Fits pasted into a fitting buy order as EFT instead of a site fitting."""

from __future__ import annotations

from dataclasses import dataclass, field

from eveuniverse.models import EveType

from fittings.eft import item_quantities, parse_eft_header

SHIP_CATEGORY_ID = 6
MAX_CUSTOM_EFT_LENGTH = 20_000


@dataclass
class CustomFit:
    """A pasted EFT block, checked against EveType names."""

    eft: str
    ship_name: str = ""
    fit_name: str = ""
    ship_id: int | None = None
    unknown_names: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


def normalize_eft(eft: str) -> str:
    lines = (eft or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).strip()


def resolve_custom_fit(eft: str) -> CustomFit:
    """
    Parse a pasted EFT block with the shared parser (``fittings.eft``) and
    resolve every name to an EveType. ``error`` explains what is wrong; for
    unknown items it lists each name that matched nothing.
    """
    text = normalize_eft(eft)
    fit = CustomFit(eft=text)
    if not text:
        fit.error = "Paste a fit in EFT format."
        return fit
    if len(text) > MAX_CUSTOM_EFT_LENGTH:
        fit.error = "That fit is too long to be one EFT block."
        return fit

    ship_name, fit_name = parse_eft_header(text)
    if not ship_name:
        fit.error = (
            "The first line must be the EFT header, like "
            "[Hurricane, My Hurricane]."
        )
        return fit
    fit.ship_name = ship_name
    fit.fit_name = fit_name or ship_name

    names = set(item_quantities(text))
    rows = EveType.objects.filter(name__in=names).values_list(
        "name", "id", "eve_group__eve_category_id"
    )
    # Exact names, as EVE and pyfa copy them: the order BOM matches names
    # exactly, so a case-only match here would drop the item later.
    by_name = {name: (type_id, cat) for name, type_id, cat in rows}

    ship = by_name.get(ship_name)
    if ship is None:
        fit.unknown_names.append(ship_name)
    elif ship[1] != SHIP_CATEGORY_ID:
        fit.error = f"{ship_name} is not a ship."
        return fit
    else:
        fit.ship_id = ship[0]

    fit.unknown_names.extend(
        sorted(
            name for name in names if name != ship_name and name not in by_name
        )
    )
    if fit.unknown_names:
        fit.error = "Unknown items: " + ", ".join(fit.unknown_names)
    return fit
