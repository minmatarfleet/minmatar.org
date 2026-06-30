from __future__ import annotations

from typing import TextIO

import requests
from django.core.management.base import BaseCommand, CommandStyle
from django.db.models import Max, Min
from django.utils import timezone

from feed.constants import R2Z2_SEQUENCE_URL, R2Z2_USER_AGENT
from feed.helpers.ingest import (
    parse_r2z2_payload,
    upsert_feed_killmail_from_r2z2,
)
from feed.helpers.killmail_classify import is_npc_kill
from feed.helpers.monitored_systems import (
    get_monitored_system_ids,
    is_monitored_system,
)
from feed.models import FeedKillmail, FeedMonitoredSystem, FeedR2z2Cursor

R2Z2_BASE = "https://r2z2.zkillboard.com/ephemeral"

ScanCounts = dict[str, int]
SampleInsert = tuple[int, int, int] | None


def _headers() -> dict[str, str]:
    return {"User-Agent": R2Z2_USER_AGENT, "Accept": "application/json"}


def _fetch_sequence_payload(sequence: int) -> requests.Response:
    return requests.get(
        f"{R2Z2_BASE}/{sequence}.json",
        headers=_headers(),
        timeout=30,
    )


def _discard_reason(payload: dict, allowlist: frozenset[int]) -> str | None:
    raw, zkb = parse_r2z2_payload(payload)[:2]
    if is_npc_kill(zkb):
        return "npc"
    solar_system_id = raw.get("solar_system_id")
    if solar_system_id is None:
        return "missing_solar_system_id"
    if not is_monitored_system(solar_system_id, allowlist):
        return "unmonitored_system"
    killmail_id = raw.get("killmail_id") or payload.get("killmail_id")
    killmail_hash = payload.get("hash") or zkb.get("hash")
    if not killmail_id:
        return "missing_killmail_id"
    if not killmail_hash:
        return "missing_hash"
    if not raw.get("killmail_time"):
        return "missing_killmail_time"
    return None


def _write_killmail_state(stdout: TextIO) -> None:
    stdout.write("=== Feed killmail state ===\n")
    km_qs = FeedKillmail.objects.all()
    agg = km_qs.aggregate(
        min_time=Min("killmail_time"),
        max_time=Max("killmail_time"),
        max_created=Max("created_at"),
    )
    stdout.write(f"  rows: {km_qs.count()}\n")
    stdout.write(f"  killmail_time: {agg['min_time']} -> {agg['max_time']}\n")
    stdout.write(f"  created_at max: {agg['max_created']}\n")


def _write_cursor_state(stdout: TextIO, cursor: FeedR2z2Cursor) -> int | None:
    stdout.write("\n=== R2Z2 cursor ===\n")
    stdout.write(f"  last_sequence_id: {cursor.last_sequence_id}\n")
    stdout.write(f"  updated_at: {cursor.updated_at}\n")
    next_sequence = (
        cursor.last_sequence_id + 1 if cursor.last_sequence_id else None
    )
    stdout.write(f"  next poll sequence: {next_sequence}\n")
    return next_sequence


def _write_allowlist_state(
    stdout: TextIO, style: CommandStyle, allowlist: frozenset[int]
) -> None:
    monitored_count = FeedMonitoredSystem.objects.filter(
        is_active=True
    ).count()
    stdout.write("\n=== Monitored systems ===\n")
    stdout.write(f"  active rows: {monitored_count}\n")
    stdout.write(f"  allowlist size: {len(allowlist)}\n")
    if not allowlist:
        stdout.write(
            style.ERROR("  ALLOWLIST EMPTY — every kill will be discarded\n")
        )


def _fetch_latest_sequence() -> int:
    response = requests.get(R2Z2_SEQUENCE_URL, headers=_headers(), timeout=30)
    response.raise_for_status()
    return int(response.json()["sequence"])


def _write_live_edge(
    stdout: TextIO,
    style: CommandStyle,
    cursor: FeedR2z2Cursor,
    next_sequence: int | None,
    latest: int,
) -> None:
    stdout.write("\n=== Live edge ===\n")
    stdout.write(f"  latest sequence: {latest}\n")
    if next_sequence is None:
        return
    gap = latest - cursor.last_sequence_id
    stdout.write(f"  sequences behind live edge: {gap}\n")
    if gap > 0:
        stdout.write(
            style.WARNING(
                "  Cursor is behind live edge; poll should process "
                f"up to {gap} sequences when run.\n"
            )
        )
    elif gap == 0:
        stdout.write(
            "  Cursor is at live edge — --once with processed=0 is "
            "expected unless a new kill arrives during the poll.\n"
        )


def _probe_next_sequence(
    stdout: TextIO,
    style: CommandStyle,
    next_sequence: int,
    allowlist: frozenset[int],
) -> None:
    stdout.write(f"\n=== Next sequence probe ({next_sequence}) ===\n")
    try:
        probe = _fetch_sequence_payload(next_sequence)
    except requests.RequestException as exc:
        stdout.write(style.ERROR(f"  probe failed: {exc}\n"))
        return

    stdout.write(f"  HTTP {probe.status_code}\n")
    if probe.status_code == 404:
        stdout.write("  404 = caught up (or stuck behind expired sequences)\n")
        return
    if not probe.ok:
        return

    payload = probe.json()
    reason = _discard_reason(payload, allowlist)
    if reason:
        stdout.write(f"  would discard: {reason}\n")
        return
    raw = parse_r2z2_payload(payload)[0]
    stdout.write(
        f"  would insert: killmail_id={raw.get('killmail_id')} "
        f"system={raw.get('solar_system_id')}\n"
    )


def _empty_scan_counts() -> ScanCounts:
    return {
        "ok": 0,
        "npc": 0,
        "unmonitored_system": 0,
        "missing_fields": 0,
        "http_error": 0,
    }


def _scan_sequences(
    latest: int, scan: int, allowlist: frozenset[int]
) -> tuple[ScanCounts, SampleInsert, int]:
    start = max(1, latest - scan + 1)
    counts = _empty_scan_counts()
    sample_insert: SampleInsert = None

    for sequence in range(start, latest + 1):
        try:
            response = _fetch_sequence_payload(sequence)
        except requests.RequestException:
            counts["http_error"] += 1
            continue
        if response.status_code != 200:
            counts["http_error"] += 1
            continue

        payload = response.json()
        reason = _discard_reason(payload, allowlist)
        if reason is None:
            counts["ok"] += 1
            raw = parse_r2z2_payload(payload)[0]
            if sample_insert is None:
                sample_insert = (
                    sequence,
                    raw.get("killmail_id"),
                    raw.get("solar_system_id"),
                )
        elif reason == "npc":
            counts["npc"] += 1
        elif reason == "unmonitored_system":
            counts["unmonitored_system"] += 1
        else:
            counts["missing_fields"] += 1

    return counts, sample_insert, start


def _write_scan_results(
    stdout: TextIO,
    style: CommandStyle,
    *,
    scan: int,
    start: int,
    latest: int,
    counts: ScanCounts,
    sample_insert: SampleInsert,
    allowlist: frozenset[int],
    dry_run: bool,
) -> None:
    stdout.write(f"\n=== Scan last {scan} sequences ===\n")
    stdout.write(f"  range: {start} .. {latest}\n")
    for key, value in counts.items():
        stdout.write(f"  {key}: {value}\n")

    if not sample_insert:
        stdout.write(
            "  no monitored-system kills in scan window "
            "(normal for small --scan values)\n"
        )
        return

    seq, killmail_id, system_id = sample_insert
    name = (
        FeedMonitoredSystem.objects.filter(solar_system_id=system_id)
        .values_list("name", flat=True)
        .first()
    )
    stdout.write(
        f"  sample insertable: seq={seq} kill={killmail_id} "
        f"system={system_id} ({name})\n"
    )
    if dry_run:
        return

    response = _fetch_sequence_payload(seq)
    if not response.ok:
        return
    result = upsert_feed_killmail_from_r2z2(
        response.json(), allowlist=allowlist
    )
    if result:
        stdout.write(
            style.SUCCESS(f"  imported killmail {result.killmail_id}\n")
        )
    else:
        stdout.write(
            style.WARNING("  upsert returned None after scan said ok\n")
        )


class Command(BaseCommand):
    help = (
        "Diagnose R2Z2 feed ingestion: cursor vs live edge, allowlist, "
        "and sample discard reasons"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--scan",
            type=int,
            default=100,
            help="How many recent sequences to scan for a monitored-system kill",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not write killmails while scanning",
        )

    def handle(self, *args, **options):
        scan = max(1, options["scan"])
        dry_run = options["dry_run"]
        allowlist = get_monitored_system_ids(force_refresh=True)

        _write_killmail_state(self.stdout)
        next_sequence = _write_cursor_state(
            self.stdout, FeedR2z2Cursor.get_singleton()
        )
        _write_allowlist_state(self.stdout, self.style, allowlist)

        try:
            latest = _fetch_latest_sequence()
        except requests.RequestException as exc:
            self.stdout.write(
                self.style.ERROR(f"\nsequence.json failed: {exc}")
            )
            return

        cursor = FeedR2z2Cursor.get_singleton()
        _write_live_edge(
            self.stdout, self.style, cursor, next_sequence, latest
        )
        if next_sequence is not None:
            _probe_next_sequence(
                self.stdout, self.style, next_sequence, allowlist
            )

        counts, sample_insert, start = _scan_sequences(latest, scan, allowlist)
        _write_scan_results(
            self.stdout,
            self.style,
            scan=scan,
            start=start,
            latest=latest,
            counts=counts,
            sample_insert=sample_insert,
            allowlist=allowlist,
            dry_run=dry_run,
        )
        self.stdout.write(f"\n(now: {timezone.now().isoformat()})\n")
