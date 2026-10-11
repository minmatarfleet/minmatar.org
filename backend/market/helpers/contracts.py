import logging
import math
from datetime import datetime, timedelta
from statistics import median
from typing import Iterable, List

import pytz
from django.db.models import Count, Q
from django.utils import timezone

from eveonline.models import EveCharacter, EveCorporation, EveLocation
from fittings.forms import normalize_fitting_aliases
from fittings.models import EveFitting

from market.helpers.contract_match import strip_fitting_tag
from market.helpers.health_common import windowed_count
from market.models import (
    EveMarketContract,
    EveMarketContractError,
    EveMarketContractExpectation,
)

logger = logging.getLogger(__name__)

# Finished contracts within this gap count as one fleet "burst".
CONTRACT_BURST_GAP = timedelta(minutes=45)
CONTRACT_BURST_LOOKBACK_DAYS = 30

CONTRACT_VOLUME_WINDOWS = (7, 30, 90, 365)
UNSTOCKED_PCT_DAYS = 30

# pylint: disable=W1405


class MarketContractHistoricalQuantity:
    date: str
    quantity: int

    def __init__(self, date: str, quantity: int):
        self.date = date
        self.quantity = quantity


def get_historical_quantity(
    expectation: EveMarketContractExpectation,
) -> List[MarketContractHistoricalQuantity]:
    """Historical finished contract counts for an expectation's fitting (and location)."""
    return get_historical_quantity_for_fitting(
        expectation.fitting, location=expectation.location
    )


def get_historical_quantity_for_fitting(
    fitting: EveFitting,
    location: EveLocation | None = None,
) -> List[MarketContractHistoricalQuantity]:
    """Historical finished contract counts per month for a fitting, optionally at a location."""
    historical_quantity = []
    today = datetime.today()
    utc = pytz.UTC
    for i in range(12):
        month_start = (
            today.replace(day=1, tzinfo=utc) - timedelta(days=i * 30)
        ).replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1)
        qs = EveMarketContract.objects.filter(
            fitting=fitting,
            status="finished",
            completed_at__gte=month_start,
            completed_at__lt=month_end,
        )
        if location is not None:
            qs = qs.filter(location=location)
        historical_quantity.append(
            MarketContractHistoricalQuantity(
                date=month_start.strftime("%Y-%m-%d"),
                quantity=qs.count(),
            )
        )

    return historical_quantity


def finished_contract_volume_windows_by_fitting(
    *,
    location: EveLocation,
    fitting_ids: Iterable[int],
    windows: tuple[int, ...] = CONTRACT_VOLUME_WINDOWS,
) -> dict[int, dict[int, int]]:
    """Finished-contract counts per fitting for each rolling window.

    Returns ``{fitting_id: {days: volume}}``. Requested fittings always
    appear; missing volume is 0.
    """
    fitting_id_list = [fid for fid in fitting_ids if fid is not None]
    empty = {days: 0 for days in windows}
    if not fitting_id_list:
        return {}

    now = timezone.now()
    max_days = max(windows)
    since = now - timedelta(days=max_days)
    volumes: dict[int, dict[int, int]] = {
        fid: dict(empty) for fid in fitting_id_list
    }
    annotations = {
        f"volume_{days}d": (
            Count("id")
            if days == max_days
            else windowed_count(now - timedelta(days=days))
        )
        for days in windows
    }
    for row in (
        EveMarketContract.objects.filter(
            location=location,
            status="finished",
            fitting_id__in=fitting_id_list,
            completed_at__gte=since,
        )
        .values("fitting_id")
        .annotate(**annotations)
    ):
        volumes[row["fitting_id"]] = {
            days: int(row[f"volume_{days}d"]) for days in windows
        }
    return volumes


def finished_contract_volume_by_fitting(
    *,
    location: EveLocation,
    fitting_ids: Iterable[int],
    days: int = 28,
) -> dict[int, int]:
    """Finished-contract counts per fitting at a location for a rolling window.

    Returns ``{fitting_id: volume}``. Missing fittings are omitted (callers
    should default to 0).
    """
    windows = finished_contract_volume_windows_by_fitting(
        location=location,
        fitting_ids=fitting_ids,
        windows=(days,),
    )
    return {
        fitting_id: counts.get(days, 0)
        for fitting_id, counts in windows.items()
        if counts.get(days, 0)
    }


def merge_stock_intervals(
    intervals: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    """Merge overlapping listing intervals into a covering union."""
    if not intervals:
        return []
    ordered = sorted((start, end) for start, end in intervals if end > start)
    if not ordered:
        return []
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def unstocked_pct_by_fitting(
    *,
    location: EveLocation,
    fitting_ids: Iterable[int],
    days: int = UNSTOCKED_PCT_DAYS,
) -> dict[int, int]:
    """Share of the window with no outstanding contracts, per fitting.

    Presence target: in stock whenever at least one contract is listed.
    Reconstructed from issued/completed/expiry timestamps. Returns 0–100.
    """
    fitting_id_list = [fid for fid in fitting_ids if fid is not None]
    if not fitting_id_list:
        return {}

    now = timezone.now()
    window_start = now - timedelta(days=days)
    window_seconds = (now - window_start).total_seconds()
    if window_seconds <= 0:
        return {fid: 0 for fid in fitting_id_list}

    overlapping = Q(status="outstanding") | Q(completed_at__gte=window_start)
    overlapping |= Q(expires_at__gte=window_start)
    overlapping |= Q(last_updated__gte=window_start)
    overlapping |= Q(issued_at__gte=window_start)

    intervals_by_fit: dict[int, list[tuple[datetime, datetime]]] = {
        fid: [] for fid in fitting_id_list
    }
    for row in EveMarketContract.objects.filter(
        overlapping,
        location=location,
        fitting_id__in=fitting_id_list,
    ).values(
        "fitting_id",
        "status",
        "issued_at",
        "created_at",
        "completed_at",
        "expires_at",
        "last_updated",
    ):
        fitting_id = row["fitting_id"]
        if fitting_id not in intervals_by_fit:
            continue
        start = row["issued_at"] or row["created_at"]
        if start is None:
            continue
        if row["status"] == "outstanding":
            end = now
        else:
            end = (
                row["completed_at"]
                or row["expires_at"]
                or row["last_updated"]
                or now
            )
        start = max(start, window_start)
        end = min(end, now)
        if end > start:
            intervals_by_fit[fitting_id].append((start, end))

    result: dict[int, int] = {}
    for fitting_id, intervals in intervals_by_fit.items():
        in_stock = sum(
            (end - start).total_seconds()
            for start, end in merge_stock_intervals(intervals)
        )
        unstocked = max(0.0, 1.0 - (in_stock / window_seconds))
        result[fitting_id] = int(round(unstocked * 100))
    return result


def cluster_completion_bursts(
    completed_ats: list[datetime],
    *,
    gap: timedelta = CONTRACT_BURST_GAP,
) -> list[int]:
    """Return burst sizes from sorted completion times (gap starts a new burst)."""
    if not completed_ats:
        return []
    times = sorted(t for t in completed_ats if t is not None)
    if not times:
        return []
    bursts: list[int] = []
    size = 1
    for prev, nxt in zip(times, times[1:]):
        if nxt - prev <= gap:
            size += 1
        else:
            bursts.append(size)
            size = 1
    bursts.append(size)
    return bursts


def estimate_contract_burst_size(bursts: list[int]) -> int | None:
    """Typical fleet pull size: median of multi-buy bursts, else median of all."""
    if not bursts:
        return None
    multi = [size for size in bursts if size >= 2]
    sample = multi if multi else bursts
    return max(1, int(median(sample)))


def fleets_remaining_from_stock(
    outstanding: int,
    burst_size: int | None,
) -> int | None:
    """How many typical fleet pulls the outstanding stock covers."""
    if burst_size is None or burst_size < 1:
        return None
    if outstanding <= 0:
        return 0
    return int(math.ceil(outstanding / burst_size))


def finished_contract_burst_size_by_fitting(
    *,
    location: EveLocation,
    fitting_ids: Iterable[int],
    lookback_days: int = CONTRACT_BURST_LOOKBACK_DAYS,
    gap: timedelta = CONTRACT_BURST_GAP,
) -> dict[int, int]:
    """Typical burst size per fitting from finished contracts at a location.

    Returns ``{fitting_id: burst_size}``. Fittings without finishes omitted.
    """
    fitting_id_list = [fid for fid in fitting_ids if fid is not None]
    if not fitting_id_list:
        return {}

    since = timezone.now() - timedelta(days=lookback_days)
    times_by_fitting: dict[int, list[datetime]] = {}
    for fitting_id, completed_at in (
        EveMarketContract.objects.filter(
            location=location,
            status="finished",
            fitting_id__in=fitting_id_list,
            completed_at__gte=since,
            completed_at__isnull=False,
        )
        .order_by("fitting_id", "completed_at")
        .values_list("fitting_id", "completed_at")
    ):
        times_by_fitting.setdefault(fitting_id, []).append(completed_at)

    burst_sizes: dict[int, int] = {}
    for fitting_id, times in times_by_fitting.items():
        size = estimate_contract_burst_size(
            cluster_completion_bursts(times, gap=gap)
        )
        if size is not None:
            burst_sizes[fitting_id] = size
    return burst_sizes


# In-memory cache for get_fitting_for_contract (public contract title -> fitting)
fitting_cache = {}


def get_fitting_for_contract(contract_summary: str) -> EveFitting | None:
    if contract_summary is None or contract_summary.strip() == "":
        return None

    if contract_summary in fitting_cache:
        return fitting_cache[contract_summary]

    contract_summary = contract_summary.replace("[FLEET]", "[FL33T]")
    normalized_title = contract_summary.lower().strip()

    fitting = EveFitting.all_objects.filter(
        name__iexact=contract_summary
    ).first()
    if fitting:
        fitting_cache[contract_summary] = fitting
        return fitting

    for candidate in EveFitting.all_objects.exclude(
        aliases__isnull=True
    ).exclude(aliases=""):
        aliases = normalize_fitting_aliases(candidate.aliases)
        if not aliases:
            continue
        for alias in aliases.split(","):
            if alias.strip().lower() == normalized_title:
                fitting_cache[contract_summary] = candidate
                return candidate

    # Unique tag-stripped match: "Buffer Apostle" -> "[FL33T] Buffer Apostle"
    bare_title = strip_fitting_tag(contract_summary)
    if not bare_title:
        return None
    matches = [
        candidate
        for candidate in EveFitting.all_objects.filter(deleted__isnull=True)
        if strip_fitting_tag(candidate.name) == bare_title
    ]
    if len(matches) == 1:
        fitting_cache[contract_summary] = matches[0]
        return matches[0]

    return None


# Terminal ESI statuses that are not a completed sale — do not count as stock.
_TERMINAL_NON_SALE_STATUSES = frozenset(
    {
        "expired",
        "deleted",
        "cancelled",
        "rejected",
        "failed",
        "reversed",
    }
)


def _map_contract_status(esi_status: str) -> str:
    """Map ESI contract status to EveMarketContract status_choices.

    Unknown / unexpected statuses map to expired so they cannot inflate stock.
    """
    if esi_status in ("outstanding", "in_progress"):
        return "outstanding"
    if esi_status in ("finished", "finished_issuer", "finished_contractor"):
        return "finished"
    if esi_status in _TERMINAL_NON_SALE_STATUSES:
        return "expired"
    if esi_status:
        logger.warning(
            "Unknown ESI contract status %r; mapping to expired", esi_status
        )
    return "expired"


def create_or_update_contract_from_db_contract(
    db_contract, location: EveLocation
) -> bool:
    """
    Create or update EveMarketContract from an EveCharacterContract or
    EveCorporationContract. Stores item_exchange contracts at the location.
    Title is a hint when it matches a known fitting (exact / alias / unique
    tag-strip); items later assign or correct the fit.

    Once items have been fetched and a content match frozen, fitting/match_score
    are not overwritten from the contract title.
    """
    if db_contract.type != EveMarketContract.esi_contract_type:
        logger.info(
            "Skipping contract %s: type %s is not %s",
            db_contract.contract_id,
            db_contract.type,
            EveMarketContract.esi_contract_type,
        )
        return False
    if db_contract.start_location_id != location.location_id:
        logger.info(
            "Skipping contract %s: start_location_id %s does not match location %s",
            db_contract.contract_id,
            db_contract.start_location_id,
            location.location_id,
        )
        return False
    fitting = get_fitting_for_contract(db_contract.title or "")
    status = _map_contract_status(db_contract.status or "")
    issuer_corporation_id = None
    if getattr(db_contract, "for_corporation", False):
        issuer_corporation_id = getattr(
            db_contract, "issuer_corporation_id", None
        )
    contract, _ = EveMarketContract.objects.get_or_create(
        id=db_contract.contract_id,
        defaults={
            "price": db_contract.price or 0,
            "issuer_external_id": db_contract.issuer_id,
            "issuer_corporation_id": issuer_corporation_id,
            "fitting": fitting,
        },
    )
    contract.title = db_contract.title or ""
    contract.status = status
    contract.issued_at = db_contract.date_issued
    contract.expires_at = db_contract.date_expired
    contract.completed_at = db_contract.date_completed
    if not contract.items_fetched:
        contract.fitting = fitting
    contract.location = location
    contract.is_public = False
    contract.assignee_id = db_contract.assignee_id
    contract.acceptor_id = db_contract.acceptor_id
    contract.issuer_external_id = db_contract.issuer_id
    contract.issuer_corporation_id = issuer_corporation_id
    contract.last_updated = timezone.now()
    contract.save()
    return True


def create_or_update_contract(esi_contract, location: EveLocation):
    if not esi_contract["type"] == EveMarketContract.esi_contract_type:
        return
    if not esi_contract["start_location_id"] == location.location_id:
        return

    fitting = get_fitting_for_contract(esi_contract["title"])

    contract, _ = EveMarketContract.objects.get_or_create(
        id=esi_contract["contract_id"],
        defaults={
            "price": esi_contract["price"],
            "issuer_external_id": esi_contract["issuer_id"],
            "issuer_corporation_id": (
                esi_contract.get("issuer_corporation_id")
                if esi_contract.get("for_corporation")
                else None
            ),
            "fitting": fitting,
        },
    )
    contract.title = esi_contract["title"]
    contract.status = "outstanding"
    contract.issued_at = esi_contract.get("date_issued")
    contract.expires_at = esi_contract.get("date_expired")
    if not contract.items_fetched:
        contract.fitting = fitting
    contract.location = location
    contract.is_public = True
    contract.issuer_external_id = esi_contract["issuer_id"]
    contract.issuer_corporation_id = (
        esi_contract.get("issuer_corporation_id")
        if esi_contract.get("for_corporation")
        else None
    )
    contract.last_updated = timezone.now()
    contract.save()


def record_unmatched_market_contract(contract: EveMarketContract):
    """Record a public contract that items could not assign to a catalog fit."""
    if not contract.is_public or not contract.location_id:
        return
    record_unmatched_contract(
        {
            "contract_id": contract.id,
            "issuer_id": contract.issuer_external_id,
            "title": contract.title,
        },
        contract.location,
    )


def record_unmatched_contract(esi_contract, location: EveLocation):
    logger.info(
        "Public contract %s did not match a catalog fit: %s",
        esi_contract["contract_id"],
        esi_contract["title"],
    )
    char = EveCharacter.objects.filter(
        character_id=esi_contract["issuer_id"]
    ).first()
    corp = (
        EveCorporation.objects.filter(corporation_id=char.corporation_id)
        .select_related("alliance")
        .first()
        if char and char.corporation_id
        else None
    )
    if corp and corp.alliance and corp.alliance.ticker in ["FL33T", "BUILD"]:
        contract_error, created = EveMarketContractError.objects.get_or_create(
            location=location,
            issuer=char,
            title=esi_contract["title"],
            defaults={
                "quantity": 1,
            },
        )
        if not created:
            contract_error.quantity += 1
            contract_error.save()


def update_completed_contracts(cutoff: datetime) -> int:
    updated = (
        EveMarketContract.objects.filter(status="outstanding")
        .filter(is_public=True)
        .filter(expires_at__gt=cutoff)
        .filter(last_updated__lt=cutoff)
        .update(status="finished")
    )
    logger.info("Set %d public contracts to finished status", updated)
    return updated


def update_expired_contracts(cutoff: datetime) -> int:
    """Mark outstanding contracts past expires_at as expired (public and private)."""
    updated = (
        EveMarketContract.objects.filter(status="outstanding")
        .filter(expires_at__lt=cutoff)
        .update(status="expired")
    )
    logger.info("Set %d contracts to expired status", updated)
    return updated
