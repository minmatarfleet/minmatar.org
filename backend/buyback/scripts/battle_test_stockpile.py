"""
Battle-test buyback ledger vs hangar stockpile against production_readonly.

Read-only. Run from backend/:
  pipenv run python manage.py shell < buyback/scripts/battle_test_stockpile.py

Or:
  pipenv run python manage.py shell -c "from buyback.scripts.battle_test_stockpile import main; main()"
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from django.db import connections
from django.db.models import Sum
from django.utils import timezone
from eveuniverse.models import EveType

from buyback.models import (
    BuybackAcceptedItem,
    BuybackHangarSnapshot,
    BuybackLedgerEntry,
    BuybackPurchaseOrder,
    BuybackPurchaseOrderLine,
)

DB = "production_readonly"


def qs(model):
    return model.objects.using(DB)


def table_exists(name: str) -> bool:
    with connections[DB].cursor() as cursor:
        cursor.execute("SHOW TABLES LIKE %s", [name])
        return cursor.fetchone() is not None


@dataclass
class Issue:
    severity: str
    code: str
    detail: str


@dataclass
class Report:
    issues: list[Issue] = field(default_factory=list)

    def add(self, severity: str, code: str, detail: str) -> None:
        self.issues.append(Issue(severity, code, detail))

    def ok(self) -> bool:
        return not any(i.severity in ("critical", "high") for i in self.issues)


def type_name(type_id: int) -> str:
    row = qs(EveType).filter(id=type_id).values_list("name", flat=True).first()
    return row or f"type:{type_id}"


def ledger_totals() -> dict[str, dict[int, int]]:
    out: dict[str, dict[int, int]] = defaultdict(dict)
    rows = (
        qs(BuybackLedgerEntry)
        .values("reason", "eve_type_id")
        .annotate(total=Sum("quantity"))
    )
    for row in rows:
        qty = int(row["total"] or 0)
        if qty:
            out[row["reason"]][int(row["eve_type_id"])] = qty
    return out


def main() -> None:  # noqa: C901
    report = Report()
    print("=== Buyback stockpile battle test (production_readonly) ===\n")

    has_purchase_orders = table_exists("buyback_buybackpurchaseorder")
    if not has_purchase_orders:
        print(
            "Note: purchase order tables not deployed yet — testing ledger + hangar only.\n"
        )

    snapshot = qs(BuybackHangarSnapshot).order_by("-taken_at").first()
    snapshot_map: dict[int, int] = {}
    snapshot_at = None
    if snapshot is not None:
        snapshot_at = snapshot.taken_at
        for key, qty in (snapshot.quantities or {}).items():
            try:
                snapshot_map[int(key)] = int(qty)
            except (TypeError, ValueError):
                continue

    ledger = ledger_totals()
    inbound = ledger.get("in_contract", {})
    outbound = ledger.get("sold_contract", {})
    sold_order = ledger.get("sold_order", {})
    unknown = ledger.get("unknown", {})

    pending: dict[int, int] = {}
    if has_purchase_orders:
        for row in (
            qs(BuybackPurchaseOrderLine)
            .filter(order__status=BuybackPurchaseOrder.Status.PENDING)
            .values("eve_type_id")
            .annotate(total=Sum("quantity"))
        ):
            qty = int(row["total"] or 0)
            if qty:
                pending[int(row["eve_type_id"])] = qty

    # --- 1: Snapshot freshness ---
    print("1) Hangar snapshot (physical truth for stocks page)")
    if snapshot_at is None:
        report.add(
            "critical",
            "no_snapshot",
            "No BuybackHangarSnapshot in production.",
        )
        print("   MISSING\n")
    else:
        age_h = (timezone.now() - snapshot_at).total_seconds() / 3600
        total_units = sum(snapshot_map.values())
        print(f"   At: {snapshot_at.isoformat()} ({age_h:.1f}h ago)")
        print(f"   Types: {len(snapshot_map)} | Total units: {total_units:,}")
        if age_h > 48:
            report.add(
                "medium", "stale_snapshot", f"Snapshot is {age_h:.0f}h old."
            )
        print()

    # --- 2: Example walkthrough — top items by hangar qty ---
    print("2) Worked examples — top hangar items")
    top_hangar = sorted(
        snapshot_map.items(), key=lambda x: x[1], reverse=True
    )[:5]
    for tid, physical in top_hangar:
        inn = inbound.get(tid, 0)
        out = outbound.get(tid, 0)
        mkt = sold_order.get(tid, 0)
        implied = inn - out
        pend = pending.get(tid, 0)
        available = max(physical - pend, 0)
        fill_pool = max(min(inn - out - pend, physical - pend), 0)
        print(f"   {type_name(tid)}")
        print(
            f"     hangar={physical:,}  in_contract={inn:,}  sold_contract={out:,}  sold_order={mkt:,}"
        )
        print(f"     ledger_implied(on-hand)={implied:,}  pending={pend:,}")
        print(
            f"     → stocks page would show {available:,} | fill would allow {fill_pool:,}"
        )
        if physical > implied + max(physical * 0.1, 5000):
            report.add(
                "medium",
                "hangar_above_ledger",
                f"{type_name(tid)}: hangar {physical:,} >> ledger implied {implied:,}",
            )
        if implied < 0:
            report.add(
                "critical",
                "negative_ledger_implied",
                f"{type_name(tid)}: outbound {out:,} exceeds inbound {inn:,}",
            )
        if available != fill_pool:
            report.add(
                "high",
                "stocks_fill_mismatch",
                f"{type_name(tid)}: stocks={available:,} fill={fill_pool:,}",
            )
    print()

    # --- 3: Global ledger sanity ---
    print("3) Ledger totals by reason")
    for reason in ("in_contract", "sold_contract", "sold_order", "unknown"):
        total = sum(ledger.get(reason, {}).values())
        types = len(ledger.get(reason, {}))
        print(f"   {reason:14} {types:4} types  {total:>15,} units")
    if unknown:
        report.add(
            "medium",
            "unknown_ledger",
            f"{sum(unknown.values()):,} units in unknown rows.",
        )
    print()

    # --- 4: Negative implied anywhere ---
    print("4) Types where outbound > inbound (would break fill math)")
    negatives = []
    for tid in set(inbound) | set(outbound):
        implied = inbound.get(tid, 0) - outbound.get(tid, 0)
        if implied < 0:
            negatives.append((tid, inbound.get(tid, 0), outbound.get(tid, 0)))
    if negatives:
        for tid, inn, out in negatives[:10]:
            report.add(
                "critical",
                "over_sold_ledger",
                f"{type_name(tid)}: sold_contract {out:,} > in_contract {inn:,}",
            )
            print(f"   CRITICAL {type_name(tid)}: in={inn:,} out={out:,}")
    else:
        print("   OK: no type has more sold_contract than in_contract")
    print()

    # --- 5: Hangar vs ledger implied (all types with drift) ---
    print("5) Largest hangar vs ledger-implied drift")
    deltas = []
    for tid in set(snapshot_map) | set(inbound) | set(outbound):
        physical = snapshot_map.get(tid, 0)
        implied = inbound.get(tid, 0) - outbound.get(tid, 0)
        delta = physical - implied
        if delta != 0:
            deltas.append((abs(delta), tid, physical, implied, delta))
    deltas.sort(reverse=True)
    for _, tid, physical, implied, delta in deltas[:10]:
        note = ""
        if sold_order.get(tid, 0) and delta < 0:
            note = " (market sells in ledger but not in remaining formula)"
        print(
            f"   {type_name(tid)}: hangar={physical:,} implied={implied:,} "
            f"Δ={delta:+,}{note}"
        )
    print(
        "   Drift is normal when: hangar snapshot lags, items moved without contract sync,"
    )
    print(
        "   or sold_order market fills reduced physical stock without sold_contract rows."
    )
    print()

    # --- 6: Accepted catalog vs hangar ---
    print("6) Accepted items: in hangar but ledger says zero inbound")
    accepted = {
        int(row["eve_type_id"]): row["eve_type__name"]
        for row in qs(BuybackAcceptedItem)
        .filter(active=True)
        .values("eve_type_id", "eve_type__name")
    }
    ghost = []
    for tid, name in accepted.items():
        if snapshot_map.get(tid, 0) > 0 and inbound.get(tid, 0) == 0:
            ghost.append((tid, name, snapshot_map[tid]))
    if ghost:
        for tid, name, qty in ghost[:8]:
            print(f"   {name}: {qty:,} in hangar, 0 in_contract ledger rows")
        report.add(
            "medium",
            "hangar_without_inbound",
            f"{len(ghost)} accepted type(s) in hangar with no in_contract ledger.",
        )
    else:
        print("   OK: every accepted hangar item has inbound ledger history")
    print()

    # --- 7: Recent sales trail ---
    print("7) Recent sales (last 14 days) — append-only ledger")
    cutoff = timezone.now() - timezone.timedelta(days=14)
    recent = list(
        qs(BuybackLedgerEntry)
        .filter(
            reason__in=[
                BuybackLedgerEntry.Reason.SOLD_ORDER,
                BuybackLedgerEntry.Reason.SOLD_CONTRACT,
            ],
            occurred_at__gte=cutoff,
        )
        .select_related("eve_type")
        .order_by("-occurred_at")[:15]
    )
    if not recent:
        print("   (no sales in window)")
    for entry in recent:
        print(
            f"   {entry.occurred_at.date()} [{entry.reason}] "
            f"{entry.quantity:,}×{entry.eve_type.name} "
            f"→ {entry.counterparty_name or entry.counterparty_id or '?'}"
        )
    print()

    # --- 8: Duplicate source guard (unique constraint health) ---
    print("8) Ledger row counts vs distinct (reason, source_id, type) keys")
    total_rows = qs(BuybackLedgerEntry).count()
    distinct_keys = (
        qs(BuybackLedgerEntry)
        .values("reason", "source_id", "eve_type_id")
        .distinct()
        .count()
    )
    print(f"   Rows: {total_rows:,} | Distinct keys: {distinct_keys:,}")
    if total_rows != distinct_keys:
        report.add(
            "high",
            "duplicate_ledger_keys",
            f"{total_rows - distinct_keys} duplicate (reason, source_id, type) rows.",
        )
    else:
        print(
            "   OK: upsert keys are unique (append-only via update_or_create)"
        )
    print()

    # --- 9: Pending orders (if deployed) ---
    if has_purchase_orders:
        print("9) Pending purchase reservations")
        pending_orders = list(
            qs(BuybackPurchaseOrder)
            .filter(status=BuybackPurchaseOrder.Status.PENDING)
            .prefetch_related("lines")
            .order_by("created_at", "pk")
        )
        print(f"   {len(pending_orders)} pending order(s)")
        for order in pending_orders[:5]:
            lines = ", ".join(
                f"{line.quantity:,}×{line.name}" for line in order.lines.all()
            )
            print(f"   #{order.id} {order.character_name}: {lines}")
        print()

    # --- Summary ---
    print("=== Summary ===")
    by_sev = defaultdict(list)
    for issue in report.issues:
        by_sev[issue.severity].append(issue)
    for sev in ("critical", "high", "medium", "low"):
        items = by_sev.get(sev, [])
        if items:
            print(f"\n{sev.upper()} ({len(items)}):")
            for item in items:
                print(f"  [{item.code}] {item.detail}")

    if report.ok():
        print(
            "\nVERDICT: PASS — ledger reservation math is consistent with production data."
        )
        print(
            "Stockpile accuracy depends on: fresh hangar snapshots + contract ledger sync."
        )
    else:
        print("\nVERDICT: REVIEW — critical/high issues need attention.")


if __name__ == "__main__":
    main()
