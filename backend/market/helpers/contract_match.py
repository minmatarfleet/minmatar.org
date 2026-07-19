import re
from collections import defaultdict

from django.db.models import Q
from eveuniverse.models import EveType
from fittings.models import EveDoctrineFitting, EveFitting

from market.helpers.contract_stock import MATCH_THRESHOLD
from market.models.contract import EveMarketContractExpectation
from market.models.item import parse_eft_items

# Hull, modules, subsystems, and rigs — exclude charges/drones/paste/fuel.
_STRUCTURAL_CATEGORIES = frozenset({"Ship", "Module", "Subsystem"})

_TAG_PREFIX = re.compile(r"^\[[^\]]+\]\s*")


def strip_fitting_tag(name: str) -> str:
    """Lowercase fitting/contract title with a leading [TAG] removed."""
    return _TAG_PREFIX.sub("", (name or "").strip()).strip().lower()


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
    """Full EFT type quantities including consumables (for missing/extra display)."""
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


def fitting_structural_type_quantities(fitting: EveFitting) -> dict[int, int]:
    """
    Hull/module/subsystem quantities only.

    Bulk charges and other consumables dominate FAX fits and erase Active vs
    Buffer discrimination if left in the match score.
    """
    per_name = parse_eft_items(fitting.eft_format)
    if not per_name:
        return {}
    names = list(per_name.keys())
    type_rows = EveType.objects.filter(name__in=names).values_list(
        "name", "id", "eve_group__eve_category__name"
    )
    name_to_meta = {
        name: (type_id, category) for name, type_id, category in type_rows
    }
    aggregated = defaultdict(int)
    for name, qty in per_name.items():
        meta = name_to_meta.get(name)
        if not meta:
            continue
        type_id, category = meta
        if category not in _STRUCTURAL_CATEGORIES:
            continue
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
    Module-weighted coverage of fitting requirements.

    Score uses structural items only. Missing/extra lists still include the
    full EFT (consumables) for admin display.
    """
    score_items = fitting_structural_type_quantities(fitting)
    display_items = fitting_type_quantities(fitting)
    if not score_items and not display_items:
        return 0.0, [], []

    total_required = sum(score_items.values())
    matched = 0
    missing = []
    fit_type_ids = set(display_items.keys())
    type_names = _type_names_for_ids(fit_type_ids | set(contract_items.keys()))

    for type_id, required in score_items.items():
        have = contract_items.get(type_id, 0)
        matched += min(have, required)

    for type_id, required in display_items.items():
        have = contract_items.get(type_id, 0)
        if have < required:
            name = type_names.get(type_id, str(type_id))
            missing.append((name, required - have))

    extra = []
    for type_id, have in contract_items.items():
        required = display_items.get(type_id, 0)
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
    preferred_fitting: EveFitting | None = None,
) -> tuple[
    EveFitting | None, float, list[tuple[str, int]], list[tuple[str, int]]
]:
    """Pick the highest-scoring candidate; ties prefer preferred_fitting."""
    best_fitting = None
    best_score = -1.0
    best_missing: list[tuple[str, int]] = []
    best_extra: list[tuple[str, int]] = []
    preferred_pk = preferred_fitting.pk if preferred_fitting else None

    for fitting in candidates:
        score, missing, extra = score_contract_against_fitting(
            contract_items, fitting
        )
        if score > best_score:
            best_score = score
            best_fitting = fitting
            best_missing = missing
            best_extra = extra
            continue
        if score < best_score or best_fitting is None:
            continue
        if preferred_pk is not None and fitting.pk == preferred_pk:
            best_fitting = fitting
            best_missing = missing
            best_extra = extra
        elif preferred_pk is None and fitting.ship_id:
            if (
                fitting.ship_id in contract_items
                and best_fitting.ship_id not in contract_items
            ):
                best_fitting = fitting
                best_missing = missing
                best_extra = extra

    if best_score < 0:
        return None, 0.0, [], []
    return best_fitting, best_score, best_missing, best_extra


def is_match_accepted(score: float) -> bool:
    return score >= MATCH_THRESHOLD


def market_relevant_same_ship_candidates(
    name_fitting: EveFitting,
) -> list[EveFitting]:
    """
    Name-resolved fit plus other active same-ship fits that are on a doctrine
    or have a contract expectation (so Active Apostle is included when named).
    """
    if not name_fitting.ship_id:
        return [name_fitting]

    doctrine_ids = EveDoctrineFitting.objects.values_list(
        "fitting_id", flat=True
    )
    expectation_ids = EveMarketContractExpectation.objects.values_list(
        "fitting_id", flat=True
    )
    return list(
        EveFitting.objects.filter(
            deleted__isnull=True, ship_id=name_fitting.ship_id
        )
        .filter(
            Q(pk=name_fitting.pk)
            | Q(pk__in=doctrine_ids)
            | Q(pk__in=expectation_ids)
        )
        .order_by("name")
    )
