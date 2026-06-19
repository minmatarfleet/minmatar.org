#!/usr/bin/env python
"""
Amarr–Minmatar warzone friendly-fire (militia awox) analysis via zKillboard + ESI.

Classifies same-faction kills (Amarr-on-Amarr, Minmatar-on-Minmatar) in the four
Amarr–Minmatar FW warzone regions and compares rates across configurable breakpoints.

Usage (from backend/):
    pipenv run python scripts/fw_friendly_fire_analysis.py \\
        --start 2026-03-09 --end 2026-06-18 \\
        --breakpoint 2026-06-09 \\
        --breakpoint 2026-03-10 \\
        --output-dir scripts/outputs

    # Resume interrupted ESI fetch:
    pipenv run python scripts/fw_friendly_fire_analysis.py ... --resume
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urljoin

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ZKILL_BASE = "https://zkillboard.com/api/"
ESI_KILLMAIL = "https://esi.evetech.net/latest/killmails/{killmail_id}/{killmail_hash}/"
USER_AGENT = (
    "minmatar.org-fw-ff-analysis/1.0 "
    "(https://minmatar.org; fw friendly fire research script)"
)

# Amarr–Minmatar warzone regions only
DEFAULT_REGIONS: dict[int, str] = {
    10000036: "Devoid",
    10000038: "The Bleak Lands",
    10000030: "Heimatar",
    10000042: "Metropolis",
}

DEFAULT_FACTIONS: dict[int, str] = {
    500001: "Amarr",
    500002: "Minmatar",
}

MIN_FF_EVENTS_FOR_SIGNIFICANCE = 30
MIN_POST_DAYS_FOR_SIGNIFICANCE = 14


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ZkbMeta:
    killmail_id: int
    hash: str
    total_value: float
    awox: bool
    npc: bool
    killmail_time: datetime | None = None


@dataclass
class FriendlyFireKill:
    killmail_id: int
    killmail_time: datetime
    faction_id: int
    faction_name: str
    region_id: int | None
    solar_system_id: int
    victim_character_id: int
    victim_corporation_id: int | None
    attacker_character_ids: list[int]
    attacker_corporation_ids: list[int | None]
    strict: bool
    isk_destroyed: float
    zkb_awox: bool


@dataclass
class DailyStats:
    ff_primary: int = 0
    ff_strict: int = 0
    ff_amarr: int = 0
    ff_minmatar: int = 0
    militia_kills: int = 0
    warzone_kills: int = 0


@dataclass
class Checkpoint:
    completed_zkill_keys: set[str] = field(default_factory=set)
    fetched_killmail_ids: set[int] = field(default_factory=set)

    def save(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "completed_zkill_keys": sorted(self.completed_zkill_keys),
                    "fetched_killmail_ids": sorted(self.fetched_killmail_ids),
                }
            )
        )

    @classmethod
    def load(cls, path: Path) -> Checkpoint:
        if not path.exists():
            return cls()
        data = json.loads(path.read_text())
        return cls(
            completed_zkill_keys=set(data.get("completed_zkill_keys", [])),
            fetched_killmail_ids=set(data.get("fetched_killmail_ids", [])),
        )


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


class RateLimitedSession:
    def __init__(self, min_interval: float = 1.0):
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Encoding": "gzip",
                "Accept": "application/json",
            }
        )
        self._min_interval = min_interval
        self._last_request = 0.0

    def get(self, url: str, **kwargs) -> requests.Response:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        for attempt in range(6):
            resp = self._session.get(url, timeout=60, **kwargs)
            self._last_request = time.monotonic()
            if resp.status_code == 429:
                time.sleep(min(2**attempt * 5, 120))
                continue
            if resp.status_code in (503,):
                time.sleep(min(2**attempt * 2, 60))
                continue
            resp.raise_for_status()
            return resp
        resp.raise_for_status()
        return resp


# ---------------------------------------------------------------------------
# zKillboard ingest
# ---------------------------------------------------------------------------


def _parse_zkill_time(value: str | None) -> datetime | None:
    if not value:
        return None
    # zKill uses "Y-m-d H:i:s" UTC
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def iter_zkill_pages(
    session: RateLimitedSession,
    path_parts: list[str],
    start_dt: datetime,
    end_dt: datetime,
    checkpoint: Checkpoint,
    checkpoint_key_prefix: str,
    max_pages: int = 0,
) -> Iterator[ZkbMeta]:
    """Paginate zKill API until empty page or kills fall before start_dt."""
    page = 1
    while True:
        ck_key = f"{checkpoint_key_prefix}:page:{page}"
        if ck_key in checkpoint.completed_zkill_keys:
            page += 1
            continue

        url = urljoin(ZKILL_BASE, "/".join(path_parts + [f"page/{page}/"]))
        print(f"  zKill GET {url}", flush=True)
        resp = session.get(url)
        rows = resp.json()
        if isinstance(rows, dict) and "error" in rows:
            raise RuntimeError(f"zKill API error for {url}: {rows['error']}")
        if not rows:
            checkpoint.completed_zkill_keys.add(ck_key)
            break

        oldest_on_page: datetime | None = None
        yielded = 0
        for row in rows:
            zkb = row.get("zkb", {})
            km_id = row.get("killmail_id")
            km_hash = zkb.get("hash")
            if not km_id or not km_hash:
                continue
            km_time = _parse_zkill_time(zkb.get("killmail_time"))
            if km_time:
                oldest_on_page = km_time if oldest_on_page is None else min(
                    oldest_on_page, km_time
                )
            if km_time and km_time < start_dt:
                continue
            if km_time and km_time > end_dt:
                continue
            yielded += 1
            yield ZkbMeta(
                killmail_id=int(km_id),
                hash=km_hash,
                total_value=float(zkb.get("totalValue", 0) or 0),
                awox=bool(zkb.get("awox")),
                npc=bool(zkb.get("npc")),
                killmail_time=km_time,
            )

        checkpoint.completed_zkill_keys.add(ck_key)
        checkpoint.save_path_if_set()

        # zKill returns newest-first; stop when whole page is before window
        if oldest_on_page and oldest_on_page < start_dt:
            break
        if len(rows) < 1000:
            break
        if max_pages and page >= max_pages:
            break
        page += 1


def collect_zkill_kills(
    session: RateLimitedSession,
    regions: dict[int, str],
    factions: dict[int, str],
    start_dt: datetime,
    end_dt: datetime,
    cache_dir: Path,
    checkpoint: Checkpoint,
    ingest_region_totals: bool = True,
    max_pages: int = 0,
) -> dict[int, ZkbMeta]:
    """Return deduplicated killmail_id -> ZkbMeta from zKill."""
    kills: dict[int, ZkbMeta] = {}

    months = _months_in_range(start_dt.date(), end_dt.date())
    for year, month in months:
        ym = f"{year}-{month:02d}"
        print(f"\n=== zKill ingest {ym} ===")

        if ingest_region_totals:
            for region_id, region_name in regions.items():
                prefix = f"region:{region_id}:{ym}"
                parts = [
                    "kills",
                    f"regionID/{region_id}",
                    f"year/{year}",
                    f"month/{month}",
                ]
                print(f"Region {region_name} ({region_id})")
                for meta in iter_zkill_pages(
                    session, parts, start_dt, end_dt, checkpoint, prefix, max_pages
                ):
                    kills[meta.killmail_id] = meta

        for faction_id, faction_name in factions.items():
            for region_id, region_name in regions.items():
                prefix = f"faction:{faction_id}:region:{region_id}:{ym}"
                parts = [
                    "kills",
                    f"factionID/{faction_id}",
                    f"regionID/{region_id}",
                    f"year/{year}",
                    f"month/{month}",
                ]
                print(f"Faction {faction_name} / {region_name}")
                for meta in iter_zkill_pages(
                    session, parts, start_dt, end_dt, checkpoint, prefix, max_pages
                ):
                    kills[meta.killmail_id] = meta

    print(f"\nCollected {len(kills)} unique killmail IDs from zKill")
    manifest_path = cache_dir / "zkb_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                str(k): {
                    "hash": v.hash,
                    "total_value": v.total_value,
                    "awox": v.awox,
                    "npc": v.npc,
                    "killmail_time": v.killmail_time.isoformat()
                    if v.killmail_time
                    else None,
                }
                for k, v in kills.items()
            }
        )
    )
    return kills


def _months_in_range(start: date, end: date) -> list[tuple[int, int]]:
    months: list[tuple[int, int]] = []
    cur = date(start.year, start.month, 1)
    end_month = date(end.year, end.month, 1)
    while cur <= end_month:
        months.append((cur.year, cur.month))
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)
    return months


# ---------------------------------------------------------------------------
# ESI ingest + cache
# ---------------------------------------------------------------------------


def killmail_cache_path(cache_dir: Path, killmail_id: int) -> Path:
    return cache_dir / f"{killmail_id}.json"


def fetch_killmail(
    session: RateLimitedSession,
    meta: ZkbMeta,
    cache_dir: Path,
    checkpoint: Checkpoint,
    *,
    save_checkpoint: bool = False,
) -> dict[str, Any] | None:
    path = killmail_cache_path(cache_dir, meta.killmail_id)
    if path.exists():
        return json.loads(path.read_text())

    if meta.killmail_id in checkpoint.fetched_killmail_ids and not path.exists():
        return None

    url = ESI_KILLMAIL.format(
        killmail_id=meta.killmail_id, killmail_hash=meta.hash
    )
    try:
        resp = session.get(url)
        data = resp.json()
    except requests.HTTPError as exc:
        print(f"  ESI error killmail {meta.killmail_id}: {exc}", flush=True)
        return None

    path.write_text(json.dumps(data))
    checkpoint.fetched_killmail_ids.add(meta.killmail_id)
    if save_checkpoint and getattr(checkpoint, "_save_path", None):
        checkpoint.save(checkpoint._save_path)
    return data


def fetch_all_killmails(
    session: RateLimitedSession,
    kills: dict[int, ZkbMeta],
    cache_dir: Path,
    checkpoint: Checkpoint,
    esi_interval: float = 0.15,
) -> dict[int, dict[str, Any]]:
    esi_session = RateLimitedSession(min_interval=esi_interval)
    results: dict[int, dict[str, Any]] = {}
    total = len(kills)
    pending_save = 0
    for i, (km_id, meta) in enumerate(kills.items(), 1):
        path = killmail_cache_path(cache_dir, km_id)
        if path.exists():
            results[km_id] = json.loads(path.read_text())
            continue
        if i % 100 == 0 or i == total:
            print(f"  ESI fetch {i}/{total}...", flush=True)
        data = fetch_killmail(
            esi_session,
            meta,
            cache_dir,
            checkpoint,
            save_checkpoint=False,
        )
        if data:
            results[km_id] = data
            pending_save += 1
            if pending_save >= 50:
                if getattr(checkpoint, "_save_path", None):
                    checkpoint.save(checkpoint._save_path)
                pending_save = 0
    print(f"Loaded {len(results)} killmails from cache/ESI", flush=True)
    return results


# Attach save helper to Checkpoint (legacy hook for zKill pagination)
def _checkpoint_save(self: Checkpoint) -> None:
    if getattr(self, "_save_path", None):
        self.save(self._save_path)


Checkpoint.save_path_if_set = _checkpoint_save  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def parse_esi_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def classify_kill(
    km: dict[str, Any],
    zkb: ZkbMeta,
    regions: set[int],
    factions: dict[int, str],
) -> tuple[FriendlyFireKill | None, bool, bool]:
    """
    Returns (friendly_fire_or_none, is_militia_kill, is_warzone_player_kill).
    """
    victim = km.get("victim", {})
    victim_char = victim.get("character_id")
    if not victim_char:
        return None, False, False

    solar_system_id = km.get("solar_system_id")
    victim_faction = victim.get("faction_id")

    is_militia = victim_faction in factions
    is_warzone = bool(victim_char)

    attackers = km.get("attackers", [])
    same_faction_attackers: list[dict] = []
    if victim_faction in factions:
        for att in attackers:
            att_char = att.get("character_id")
            if not att_char or att_char == victim_char:
                continue
            if att.get("faction_id") == victim_faction:
                same_faction_attackers.append(att)

    ff_kill: FriendlyFireKill | None = None
    if same_faction_attackers and victim_faction in factions:
        victim_corp = victim.get("corporation_id")
        strict = any(
            att.get("corporation_id") != victim_corp
            for att in same_faction_attackers
        )
        ff_kill = FriendlyFireKill(
            killmail_id=km.get("killmail_id", zkb.killmail_id),
            killmail_time=parse_esi_time(km["killmail_time"]),
            faction_id=victim_faction,
            faction_name=factions[victim_faction],
            region_id=None,
            solar_system_id=solar_system_id,
            victim_character_id=victim_char,
            victim_corporation_id=victim_corp,
            attacker_character_ids=[
                att["character_id"] for att in same_faction_attackers
            ],
            attacker_corporation_ids=[
                att.get("corporation_id") for att in same_faction_attackers
            ],
            strict=strict,
            isk_destroyed=zkb.total_value,
            zkb_awox=zkb.awox,
        )

    return ff_kill, is_militia, is_warzone


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def two_proportion_z_test(
    success_a: int, total_a: int, success_b: int, total_b: int
) -> tuple[float, float]:
    """Return (z_statistic, p_value_two_tailed). Uses normal approximation."""
    if total_a == 0 or total_b == 0:
        return float("nan"), float("nan")
    p_a = success_a / total_a
    p_b = success_b / total_b
    p_pool = (success_a + success_b) / (total_a + total_b)
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / total_a + 1 / total_b))
    if se == 0:
        return float("nan"), float("nan")
    z = (p_b - p_a) / se
    # two-tailed p from standard normal
    p = math.erfc(abs(z) / math.sqrt(2))
    return z, p


def period_stats(
    daily: dict[date, DailyStats],
    start: date,
    end: date,
) -> dict[str, Any]:
    ff_primary = ff_strict = militia = warzone = 0
    ff_amarr = ff_minmatar = 0
    days = 0
    for d, stats in daily.items():
        if start <= d <= end:
            days += 1
            ff_primary += stats.ff_primary
            ff_strict += stats.ff_strict
            ff_amarr += stats.ff_amarr
            ff_minmatar += stats.ff_minmatar
            militia += stats.militia_kills
            warzone += stats.warzone_kills
    return {
        "days": days,
        "ff_primary": ff_primary,
        "ff_strict": ff_strict,
        "ff_amarr": ff_amarr,
        "ff_minmatar": ff_minmatar,
        "militia_kills": militia,
        "warzone_kills": warzone,
        "ff_per_1k_militia": (ff_primary / militia * 1000) if militia else 0,
        "ff_per_1k_warzone": (ff_primary / warzone * 1000) if warzone else 0,
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def write_reports(
    output_dir: Path,
    daily: dict[date, DailyStats],
    ff_kills: list[FriendlyFireKill],
    breakpoints: list[date],
    start: date,
    end: date,
    run_ts: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    tag = run_ts.replace(":", "").replace("-", "")[:15]

    # Daily CSV
    daily_path = output_dir / f"fw_ff_daily_{tag}.csv"
    sorted_days = sorted(daily)
    rolling_window = 7
    with daily_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "date",
                "ff_primary",
                "ff_strict",
                "ff_amarr",
                "ff_minmatar",
                "militia_kills",
                "warzone_kills",
                "ff_rate_per_1k_militia",
                "ff_rate_7d_rolling_per_1k_militia",
            ]
        )
        for idx, d in enumerate(sorted_days):
            s = daily[d]
            rate = (s.ff_primary / s.militia_kills * 1000) if s.militia_kills else ""
            window_days = sorted_days[max(0, idx - rolling_window + 1) : idx + 1]
            w_ff = sum(daily[wd].ff_primary for wd in window_days)
            w_mil = sum(daily[wd].militia_kills for wd in window_days)
            roll = (w_ff / w_mil * 1000) if w_mil else ""
            w.writerow(
                [
                    d.isoformat(),
                    s.ff_primary,
                    s.ff_strict,
                    s.ff_amarr,
                    s.ff_minmatar,
                    s.militia_kills,
                    s.warzone_kills,
                    f"{rate:.4f}" if rate != "" else "",
                    f"{roll:.4f}" if roll != "" else "",
                ]
            )

    # FF kills CSV
    kills_path = output_dir / f"fw_ff_kills_{tag}.csv"
    with kills_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "killmail_id",
                "killmail_time",
                "faction",
                "solar_system_id",
                "victim_character_id",
                "victim_corporation_id",
                "attacker_character_ids",
                "strict",
                "isk_destroyed",
                "zkb_awox",
            ]
        )
        for k in sorted(ff_kills, key=lambda x: x.killmail_time):
            w.writerow(
                [
                    k.killmail_id,
                    k.killmail_time.isoformat(),
                    k.faction_name,
                    k.solar_system_id,
                    k.victim_character_id,
                    k.victim_corporation_id,
                    ";".join(str(c) for c in k.attacker_character_ids),
                    k.strict,
                    f"{k.isk_destroyed:.2f}",
                    k.zkb_awox,
                ]
            )

    # Summary report
    report_path = output_dir / f"fw_ff_report_{tag}.txt"
    lines: list[str] = []
    lines.append("Amarr–Minmatar Warzone Friendly Fire Report")
    lines.append(f"Generated: {run_ts}")
    lines.append(f"Analysis window: {start} → {end}")
    lines.append("")
    lines.append("Definition: same-faction militia player kills (Amarr 500001 / Minmatar 500002)")
    lines.append("Regions: Devoid, Bleak Lands, Heimatar, Metropolis")
    lines.append("")

    total_stats = period_stats(daily, start, end)
    lines.append("=== Full window ===")
    _append_period_lines(lines, total_stats)

    sorted_bps = sorted(breakpoints)
    for bp in sorted_bps:
        pre_end = bp - timedelta(days=1)
        post_start = bp
        if pre_end < start or post_start > end:
            continue
        pre = period_stats(daily, start, pre_end)
        post = period_stats(daily, post_start, end)
        lines.append("")
        lines.append(f"=== Breakpoint {bp.isoformat()} ===")
        lines.append(f"Pre:  {start} → {pre_end}")
        _append_period_lines(lines, pre, indent="  ")
        lines.append(f"Post: {post_start} → {end}")
        _append_period_lines(lines, post, indent="  ")

        sufficient = (
            pre["days"] >= 1
            and post["days"] >= 1
            and pre["militia_kills"] > 0
            and post["militia_kills"] > 0
            and pre["ff_primary"] + post["ff_primary"] >= MIN_FF_EVENTS_FOR_SIGNIFICANCE
        )
        low_confidence = post["days"] < MIN_POST_DAYS_FOR_SIGNIFICANCE
        if sufficient:
            z, p = two_proportion_z_test(
                pre["ff_primary"],
                pre["militia_kills"],
                post["ff_primary"],
                post["militia_kills"],
            )
            lines.append("")
            if low_confidence:
                lines.append(
                    f"  ⚠ Post window only {post['days']} days — treat significance as preliminary"
                )
            lines.append("  Rate comparison (FF / militia kills):")
            lines.append(f"    Pre  rate: {pre['ff_per_1k_militia']:.3f} per 1k militia kills")
            lines.append(f"    Post rate: {post['ff_per_1k_militia']:.3f} per 1k militia kills")
            lines.append(f"    z-statistic: {z:.3f}, p-value (two-tailed): {p:.4f}")
            if p < 0.05:
                direction = "increased" if post["ff_per_1k_militia"] > pre["ff_per_1k_militia"] else "decreased"
                lines.append(f"    → Statistically significant: friendly fire {direction} post-breakpoint")
            else:
                lines.append("    → No statistically significant change in FF rate")
        else:
            lines.append("")
            lines.append(
                "  ⚠ Insufficient data for significance test "
                f"(need ≥ {MIN_FF_EVENTS_FOR_SIGNIFICANCE} combined FF events and militia kills in both windows)"
            )

        # Symmetric window: same number of days immediately before/after breakpoint
        sym_days = min(pre["days"], post["days"])
        if sym_days >= 7:
            sym_pre_end = bp - timedelta(days=1)
            sym_pre_start = sym_pre_end - timedelta(days=sym_days - 1)
            sym_post_start = bp
            sym_post_end = sym_post_start + timedelta(days=sym_days - 1)
            if sym_pre_start >= start and sym_post_end <= end:
                sp = period_stats(daily, sym_pre_start, sym_pre_end)
                so = period_stats(daily, sym_post_start, sym_post_end)
                lines.append("")
                lines.append(
                    f"  Symmetric {sym_days}-day windows around {bp}: "
                    f"{sym_pre_start}→{sym_pre_end} vs {sym_post_start}→{sym_post_end}"
                )
                lines.append(
                    f"    Pre  FF rate: {sp['ff_per_1k_militia']:.3f}/1k militia "
                    f"({sp['ff_primary']} FF / {sp['militia_kills']} militia kills)"
                )
                lines.append(
                    f"    Post FF rate: {so['ff_per_1k_militia']:.3f}/1k militia "
                    f"({so['ff_primary']} FF / {so['militia_kills']} militia kills)"
                )
                if sp["militia_kills"] and so["militia_kills"]:
                    z, p = two_proportion_z_test(
                        sp["ff_primary"],
                        sp["militia_kills"],
                        so["ff_primary"],
                        so["militia_kills"],
                    )
                    lines.append(f"    z={z:.3f}, p={p:.4f}")

    # Repeat attackers post latest breakpoint
    if sorted_bps:
        latest_bp = sorted_bps[-1]
        post_start_dt = datetime.combine(
            latest_bp, datetime.min.time(), tzinfo=timezone.utc
        )
        repeat: dict[int, int] = defaultdict(int)
        for k in ff_kills:
            if k.killmail_time >= post_start_dt:
                for cid in k.attacker_character_ids:
                    repeat[cid] += 1
        repeaters = [(cid, n) for cid, n in repeat.items() if n >= 3]
        if repeaters:
            lines.append("")
            lines.append(f"=== Repeat FF attackers (≥3) since {latest_bp} ===")
            for cid, n in sorted(repeaters, key=lambda x: -x[1])[:20]:
                lines.append(f"  character_id={cid}: {n} kills")

    lines.append("")
    lines.append("Output files:")
    lines.append(f"  {daily_path}")
    lines.append(f"  {kills_path}")

    report_text = "\n".join(lines)
    report_path.write_text(report_text)
    print("\n" + report_text)


def _append_period_lines(
    lines: list[str], stats: dict[str, Any], indent: str = ""
) -> None:
    lines.append(f"{indent}Days: {stats['days']}")
    lines.append(
        f"{indent}FF kills (primary / strict): {stats['ff_primary']} / {stats['ff_strict']}"
    )
    lines.append(
        f"{indent}  Amarr-on-Amarr: {stats['ff_amarr']}, Minmatar-on-Minmatar: {stats['ff_minmatar']}"
    )
    lines.append(f"{indent}Militia victim kills: {stats['militia_kills']}")
    lines.append(f"{indent}Warzone player kills: {stats['warzone_kills']}")
    lines.append(
        f"{indent}FF rate: {stats['ff_per_1k_militia']:.3f} per 1k militia kills, "
        f"{stats['ff_per_1k_warzone']:.3f} per 1k warzone kills"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    today = date.today()
    parser = argparse.ArgumentParser(
        description="Amarr–Minmatar warzone friendly-fire analysis"
    )
    parser.add_argument("--start", type=date.fromisoformat, default=date(2026, 3, 9))
    parser.add_argument("--end", type=date.fromisoformat, default=today)
    parser.add_argument(
        "--breakpoint",
        action="append",
        type=date.fromisoformat,
        default=[],
        help="Repeatable; e.g. --breakpoint 2026-06-09",
    )
    parser.add_argument(
        "--factions",
        default="500001,500002",
        help="Comma-separated faction IDs (default: Amarr + Minmatar)",
    )
    parser.add_argument(
        "--regions",
        default=",".join(str(r) for r in DEFAULT_REGIONS),
        help="Comma-separated region IDs",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("scripts/outputs"),
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("scripts/outputs/fw_ff_cache"),
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Skip zKill fetch; analyze cached killmails only",
    )
    parser.add_argument(
        "--zkill-interval",
        type=float,
        default=1.0,
        help="Seconds between zKill requests (default 1.0)",
    )
    parser.add_argument(
        "--esi-interval",
        type=float,
        default=0.15,
        help="Seconds between ESI requests (default 0.15)",
    )
    parser.add_argument(
        "--max-zkill-pages",
        type=int,
        default=0,
        help="Limit pages per zKill query (0 = unlimited; for testing)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.start > args.end:
        print("Error: --start must be <= --end", file=sys.stderr)
        return 1

    faction_ids = [int(x) for x in args.factions.split(",")]
    factions = {fid: DEFAULT_FACTIONS[fid] for fid in faction_ids if fid in DEFAULT_FACTIONS}
    region_ids = [int(x) for x in args.regions.split(",")]
    regions = {rid: DEFAULT_REGIONS[rid] for rid in region_ids if rid in DEFAULT_REGIONS}

    if not factions or not regions:
        print("Error: invalid --factions or --regions", file=sys.stderr)
        return 1

    breakpoints = args.breakpoint or [date(2026, 6, 9), date(2026, 3, 10)]

    start_dt = datetime.combine(args.start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(
        args.end, datetime.max.time().replace(microsecond=0), tzinfo=timezone.utc
    )

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = args.cache_dir / "checkpoint.json"
    checkpoint = Checkpoint.load(checkpoint_path) if args.resume else Checkpoint()
    checkpoint._save_path = checkpoint_path  # type: ignore[attr-defined]

    zkill_session = RateLimitedSession(min_interval=args.zkill_interval)

    if args.skip_ingest:
        manifest_path = args.cache_dir / "zkb_manifest.json"
        kills = {}
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            for km_id_str, meta in manifest.items():
                km_id = int(km_id_str)
                t = meta.get("killmail_time")
                kills[km_id] = ZkbMeta(
                    killmail_id=km_id,
                    hash=meta["hash"],
                    total_value=float(meta.get("total_value", 0)),
                    awox=bool(meta.get("awox")),
                    npc=bool(meta.get("npc")),
                    killmail_time=datetime.fromisoformat(t) if t else None,
                )
        else:
            for path in args.cache_dir.glob("*.json"):
                if path.name in ("checkpoint.json", "zkb_manifest.json"):
                    continue
                try:
                    km_id = int(path.stem)
                except ValueError:
                    continue
                data = json.loads(path.read_text())
                kills[km_id] = ZkbMeta(
                    killmail_id=km_id,
                    hash=data.get("killmail_hash", ""),
                    total_value=0,
                    awox=False,
                    npc=False,
                )
        print(f"Loaded {len(kills)} killmails from cache (--skip-ingest)")
    else:
        kills = collect_zkill_kills(
            zkill_session,
            regions,
            factions,
            start_dt,
            end_dt,
            args.cache_dir,
            checkpoint,
            max_pages=args.max_zkill_pages,
        )
        checkpoint.save(checkpoint_path)

    killmails = fetch_all_killmails(
        zkill_session,
        kills,
        args.cache_dir,
        checkpoint,
        esi_interval=args.esi_interval,
    )
    checkpoint.save(checkpoint_path)

    daily: dict[date, DailyStats] = defaultdict(DailyStats)
    ff_kills: list[FriendlyFireKill] = []

    for km_id, km in killmails.items():
        zkb = kills.get(km_id)
        if not zkb:
            continue
        km_time = parse_esi_time(km["killmail_time"])
        if km_time < start_dt or km_time > end_dt:
            continue

        ff, is_militia, is_warzone = classify_kill(
            km, zkb, set(regions.keys()), factions
        )
        day = km_time.date()
        if is_militia:
            daily[day].militia_kills += 1
        if is_warzone:
            daily[day].warzone_kills += 1
        if ff:
            ff_kills.append(ff)
            daily[day].ff_primary += 1
            if ff.strict:
                daily[day].ff_strict += 1
            if ff.faction_id == 500001:
                daily[day].ff_amarr += 1
            elif ff.faction_id == 500002:
                daily[day].ff_minmatar += 1

    run_ts = datetime.now(timezone.utc).isoformat()
    write_reports(
        args.output_dir,
        daily,
        ff_kills,
        breakpoints,
        args.start,
        args.end,
        run_ts,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
