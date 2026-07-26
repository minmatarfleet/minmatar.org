"""Load inferred-sale CSV rows into EveMarketInferredSale."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from eveuniverse.models import EveType

from eveonline.models import EveLocation
from market.models import EveMarketInferredSale

DEFAULT_CSV_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "amamake_inferred_sales.csv"
)
BATCH_SIZE = 2000


@dataclass(frozen=True)
class ImportInferredSalesResult:
    read: int
    created: int
    skipped_unknown_type: int
    skipped_overlap: int
    deleted_imported: int
    locations: tuple[int, ...]


def _parse_inferred_at(raw: str) -> datetime:
    value = (raw or "").strip()
    if not value:
        raise ValueError("empty inferred_at")
    parsed = parse_datetime(value)
    if parsed is None and value.endswith("Z"):
        parsed = parse_datetime(value[:-1] + "+00:00")
    if parsed is None:
        raise ValueError(f"invalid inferred_at: {raw!r}")
    if timezone.is_naive(parsed):
        parsed = parsed.replace(tzinfo=dt_timezone.utc)
    return parsed


def iter_inferred_sale_csv_rows(path: Path):
    """Yield dicts with location_id, type_id, quantity, price, inferred_at."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {
            "location_id",
            "type_id",
            "quantity",
            "price",
            "inferred_at",
        }
        if reader.fieldnames is None or required - set(reader.fieldnames):
            missing = sorted(required - set(reader.fieldnames or []))
            raise ValueError(f"CSV missing columns: {missing}")
        for row in reader:
            yield {
                "location_id": int(row["location_id"]),
                "type_id": int(row["type_id"]),
                "quantity": int(row["quantity"]),
                "price": Decimal(str(row["price"]).strip()),
                "inferred_at": _parse_inferred_at(row["inferred_at"]),
            }


def import_inferred_sales_csv(  # noqa: C901
    path: Path,
    *,
    dry_run: bool = False,
    replace_imported: bool = False,
    before_existing: bool = True,
) -> ImportInferredSalesResult:
    """
    Import CSV rows as reason=imported inferred sales.

    When ``before_existing`` is True (default), rows at or after the earliest
    existing sale for that location are skipped to avoid double-counting live
    sync data. ``replace_imported`` deletes prior ``imported`` rows for
    locations in the file before inserting.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)

    rows = list(iter_inferred_sale_csv_rows(path))
    location_ids = sorted({row["location_id"] for row in rows})
    if not location_ids:
        return ImportInferredSalesResult(0, 0, 0, 0, 0, ())

    missing_locations = set(location_ids) - set(
        EveLocation.objects.filter(location_id__in=location_ids).values_list(
            "location_id", flat=True
        )
    )
    if missing_locations:
        raise ValueError(
            "EveLocation missing for location_id(s): "
            + ", ".join(str(x) for x in sorted(missing_locations))
        )

    type_ids = {row["type_id"] for row in rows}
    known_types = set(
        EveType.objects.filter(id__in=type_ids).values_list("id", flat=True)
    )

    earliest_by_location: dict[int, datetime] = {}
    if before_existing:
        for location_id in location_ids:
            qs = EveMarketInferredSale.objects.filter(location_id=location_id)
            if replace_imported:
                qs = qs.exclude(reason=EveMarketInferredSale.REASON_IMPORTED)
            earliest = (
                qs.order_by("inferred_at")
                .values_list("inferred_at", flat=True)
                .first()
            )
            if earliest is not None:
                earliest_by_location[location_id] = earliest

    deleted_imported = 0
    to_create: list[EveMarketInferredSale] = []
    skipped_unknown = 0
    skipped_overlap = 0

    for row in rows:
        if row["type_id"] not in known_types:
            skipped_unknown += 1
            continue
        cutoff = earliest_by_location.get(row["location_id"])
        if cutoff is not None and row["inferred_at"] >= cutoff:
            skipped_overlap += 1
            continue
        try:
            price = row["price"]
            if not isinstance(price, Decimal):
                price = Decimal(str(price))
        except (InvalidOperation, TypeError) as exc:
            raise ValueError(f"invalid price in CSV: {row!r}") from exc
        to_create.append(
            EveMarketInferredSale(
                location_id=row["location_id"],
                item_id=row["type_id"],
                quantity=row["quantity"],
                price=price,
                inferred_at=row["inferred_at"],
                order_id=None,
                reason=EveMarketInferredSale.REASON_IMPORTED,
            )
        )

    if dry_run:
        return ImportInferredSalesResult(
            read=len(rows),
            created=len(to_create),
            skipped_unknown_type=skipped_unknown,
            skipped_overlap=skipped_overlap,
            deleted_imported=0,
            locations=tuple(location_ids),
        )

    with transaction.atomic():
        if replace_imported:
            deleted_imported, _ = EveMarketInferredSale.objects.filter(
                location_id__in=location_ids,
                reason=EveMarketInferredSale.REASON_IMPORTED,
            ).delete()
        for start in range(0, len(to_create), BATCH_SIZE):
            EveMarketInferredSale.objects.bulk_create(
                to_create[start : start + BATCH_SIZE]
            )

    return ImportInferredSalesResult(
        read=len(rows),
        created=len(to_create),
        skipped_unknown_type=skipped_unknown,
        skipped_overlap=skipped_overlap,
        deleted_imported=deleted_imported,
        locations=tuple(location_ids),
    )
