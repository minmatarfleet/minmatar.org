"""Build effective EFT text for fitting buy order lines (with swaps)."""

from __future__ import annotations

from eveuniverse.models import EveType

from market.models.fitting_buy_order import FittingBuyOrderLine


def replace_eft_type_name(eft: str, preferred: str, substitute: str) -> str:
    if not preferred or not substitute or preferred == substitute:
        return eft
    out: list[str] = []
    for line in eft.splitlines():
        stripped = line.strip()
        if stripped == preferred:
            out.append(line.replace(preferred, substitute, 1))
        elif stripped.startswith(f"{preferred} "):
            out.append(line.replace(preferred, substitute, 1))
        elif stripped.startswith(f"{preferred},"):
            out.append(line.replace(preferred, substitute, 1))
        else:
            out.append(line)
    return "\n".join(out)


def _swap_type_ids(swaps: list | None) -> set[int]:
    type_ids: set[int] = set()
    for swap in swaps or []:
        preferred = int(swap.get("preferred_type_id") or 0)
        substitute = int(swap.get("substitute_type_id") or 0)
        if preferred:
            type_ids.add(preferred)
        if substitute:
            type_ids.add(substitute)
    return type_ids


def _apply_swaps_to_eft(
    eft: str, swaps: list | None, names: dict[int, str]
) -> str:
    result = eft
    for swap in swaps or []:
        preferred = names.get(int(swap.get("preferred_type_id") or 0), "")
        substitute = names.get(int(swap.get("substitute_type_id") or 0), "")
        result = replace_eft_type_name(result, preferred, substitute)
    return result


def effective_eft_for_line(
    line: FittingBuyOrderLine,
    *,
    type_names: dict[int, str] | None = None,
) -> str:
    eft = line.fitting.eft_format or ""
    swaps = line.swaps or []
    if not swaps:
        return eft
    if type_names is None:
        type_ids = _swap_type_ids(swaps)
        type_names = dict(
            EveType.objects.filter(id__in=type_ids).values_list("id", "name")
        )
    return apply_swaps_to_eft(eft, swaps, type_names)


def apply_swaps_to_eft(
    eft: str, swaps: list | None, names: dict[int, str]
) -> str:
    return _apply_swaps_to_eft(eft, swaps, names)


def effective_efts_for_lines(
    lines: list[FittingBuyOrderLine],
) -> dict[int, str]:
    type_ids: set[int] = set()
    for line in lines:
        type_ids |= _swap_type_ids(line.swaps)
    names = (
        dict(EveType.objects.filter(id__in=type_ids).values_list("id", "name"))
        if type_ids
        else {}
    )
    return {
        line.id: effective_eft_for_line(line, type_names=names)
        for line in lines
    }


def bundle_effective_efts(lines: list[FittingBuyOrderLine]) -> str:
    by_id = effective_efts_for_lines(lines)
    blocks = [by_id[line.id].strip() for line in lines]
    return "\n\n".join(block for block in blocks if block)
