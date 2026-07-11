from collections import defaultdict

from eveuniverse.models import EveType
from fittings.models import EveFitting

from market.models.item import parse_eft_items

MATCH_THRESHOLD = 0.90


def normalize_contract_items(raw_items: list[dict]) -> dict[int, int]:
    """Aggregate per-slot ESI rows into {type_id: quantity} for included items."""
    aggregated = defaultdict(int)
    for row in raw_items:
        if not row.get("is_included", True):
            continue
        type_id = row["type_id"]
        quantity = row.get("quantity", 1) or 1
        aggregated[type_id] += quantity
    return dict(aggregated)


def fitting_type_quantities(fitting: EveFitting) -> dict[int, int]:
    per_name = parse_eft_items(fitting.eft_format)
    if not per_name:
        return {}
    names = list(per_name.keys())
    name_to_id = dict(
        EveType.objects.filter(name__in=names).values_list("name", "id")
    )
    aggregated = defaultdict(int)
    for name, qty in per_name.items():
        type_id = name_to_id.get(name)
        if type_id:
            aggregated[type_id] += qty
    return dict(aggregated)


def _type_names_for_ids(type_ids: set[int]) -> dict[int, str]:
    if not type_ids:
        return {}
    return {
        row["id"]: row["name"]
        for row in EveType.objects.filter(id__in=type_ids).values("id", "name")
    }


def score_contract_against_fitting(
    contract_items: dict[int, int], fitting: EveFitting
) -> tuple[float, list[tuple[str, int]], list[tuple[str, int]]]:
    """
    Quantity-weighted coverage of fitting requirements.
    Returns (score, missing, extra) where missing/extra are (item_name, qty).
    """
    fit_items = fitting_type_quantities(fitting)
    if not fit_items:
        return 0.0, [], []

    total_required = sum(fit_items.values())
    matched = 0
    missing = []
    fit_type_ids = set(fit_items.keys())
    type_names = _type_names_for_ids(fit_type_ids | set(contract_items.keys()))

    for type_id, required in fit_items.items():
        have = contract_items.get(type_id, 0)
        matched += min(have, required)
        if have < required:
            name = type_names.get(type_id, str(type_id))
            missing.append((name, required - have))

    extra = []
    for type_id, have in contract_items.items():
        required = fit_items.get(type_id, 0)
        if have > required:
            name = type_names.get(type_id, str(type_id))
            extra.append((name, have - required))
        elif type_id not in fit_type_ids:
            name = type_names.get(type_id, str(type_id))
            extra.append((name, have))

    score = matched / total_required if total_required else 0.0
    return score, missing, extra


def match_contract_to_fitting(
    contract_items: dict[int, int],
    candidates,
) -> tuple[
    EveFitting | None, float, list[tuple[str, int]], list[tuple[str, int]]
]:
    best_fitting = None
    best_score = 0.0
    best_missing: list[tuple[str, int]] = []
    best_extra: list[tuple[str, int]] = []

    for fitting in candidates:
        score, missing, extra = score_contract_against_fitting(
            contract_items, fitting
        )
        if score > best_score:
            best_score = score
            best_fitting = fitting
            best_missing = missing
            best_extra = extra
        elif score == best_score and best_fitting and fitting.ship_id:
            if (
                fitting.ship_id in contract_items
                and best_fitting.ship_id not in contract_items
            ):
                best_fitting = fitting
                best_missing = missing
                best_extra = extra

    return best_fitting, best_score, best_missing, best_extra


def is_match_accepted(score: float) -> bool:
    return score >= MATCH_THRESHOLD
