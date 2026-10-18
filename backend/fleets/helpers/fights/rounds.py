"""Cut a fleet's killmails into rounds. Pure: no database, no network.

Rows are the stored timeline killmails (see collect.py), oldest first:

    {"id", "t" (ISO time), "outcome" ("kill" | "loss"), "system", "ship",
     "victim", "victim_group", "isk", "pending", "pod",
     "pilots" (our in-fleet attackers), "hostiles" ([group, character] of
     everyone else who shot us, losses only)}

The rules, in order:

1. A new round starts after more than ``QUIET_GAP`` without a killmail.
2. A reship wave (an event from the ship snapshots) starts a new round when
   it falls in a lull of at least ``RESHIP_MIN_GAP`` inside a round.
3. FC edits: a merge drops every cut inside its interval, a split adds one.
   Splits win over merges, so the latest intent of "cut here" holds.
4. A segment with fewer than ``ROUND_MIN_SHIPS`` ships killed and lost (pods
   don't count) is a skirmish, not a numbered round.

Cuts are moments: a row starts a new segment when a cut falls after the
previous row and at or before it. That keeps edits stable when a late
killmail arrives, because nothing is keyed by round number.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Iterable
from urllib.parse import quote

QUIET_GAP = timedelta(minutes=5)
RESHIP_MIN_GAP = timedelta(minutes=2)
ROUND_MIN_SHIPS = 4
# Gaps shorter than this are not offered as split points.
SPLIT_MIN_GAP = timedelta(seconds=90)
SPLIT_GAPS_SHOWN = 4
BIGGEST_SHOWN = 6
# A live round is "fighting" while its last mail is this recent.
FIGHTING_WITHIN = QUIET_GAP
# zKill's related page covers this many hours around the hour it is given.
ZKILL_HOURS_BEFORE = 1
ZKILL_HOURS_AFTER = 2
ZKILL_MAX_HOURS = 12
ZKILL_MAX_SYSTEMS = 10
ZKILL_MAX_TEAM = 10
# Chart bars: one per minute up to this many, then wider bins.
CHART_MAX_BINS = 150

OUTCOME_KILL = "kill"
OUTCOME_LOSS = "loss"


def parse_time(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def _iso(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment else None


# --------------------------------------------------------------------- cuts


def auto_cuts(rows: list[dict]) -> set[datetime]:
    """A cut at every mail that follows a quiet gap."""
    cuts = set()
    for before, after in zip(rows, rows[1:]):
        if parse_time(after["t"]) - parse_time(before["t"]) > QUIET_GAP:
            cuts.add(parse_time(after["t"]))
    return cuts


def reship_cuts(
    rows: list[dict], events: list[dict], cuts: set[datetime]
) -> set[datetime]:
    """Cuts for reship waves that land in a lull inside a round."""
    added = set()
    reships = [
        parse_time(event["at"])
        for event in events
        if event.get("kind") == "reship"
    ]
    for wave in reships:
        for before, after in zip(rows, rows[1:]):
            start, end = parse_time(before["t"]), parse_time(after["t"])
            if not start <= wave < end:
                continue
            if end not in cuts and end - start >= RESHIP_MIN_GAP:
                added.add(end)
            break
    return added


def apply_edits(cuts: set[datetime], edits: Iterable[dict]) -> set[datetime]:
    cuts = set(cuts)
    edits = list(edits)
    for edit in edits:
        if edit["kind"] == "merge":
            start, end = parse_time(edit["start"]), parse_time(edit["end"])
            cuts = {cut for cut in cuts if not start < cut <= end}
    for edit in edits:
        if edit["kind"] == "split":
            cuts.add(parse_time(edit["start"]))
    return cuts


def split_rows(rows: list[dict], cuts: set[datetime]) -> list[list[dict]]:
    if not rows:
        return []
    ordered = sorted(cuts)
    segments = [[rows[0]]]
    for before, row in zip(rows, rows[1:]):
        prior, moment = parse_time(before["t"]), parse_time(row["t"])
        if any(prior < cut <= moment for cut in ordered):
            segments.append([row])
        else:
            segments[-1].append(row)
    return segments


def cut_segments(
    rows: list[dict], events: list[dict], edits: list[dict]
) -> list[list[dict]]:
    cuts = auto_cuts(rows)
    cuts |= reship_cuts(rows, events, cuts)
    return split_rows(rows, apply_edits(cuts, edits))


# ------------------------------------------------------------------ summary


def ship_count(rows: Iterable[dict], outcome: str) -> int:
    return sum(1 for r in rows if r["outcome"] == outcome and not r["pod"])


def is_round(rows: list[dict]) -> bool:
    return (
        ship_count(rows, OUTCOME_KILL) + ship_count(rows, OUTCOME_LOSS)
        >= ROUND_MIN_SHIPS
    )


def totals(rows: list[dict]) -> dict:
    kills = [r for r in rows if r["outcome"] == OUTCOME_KILL]
    losses = [r for r in rows if r["outcome"] == OUTCOME_LOSS]
    destroyed = sum(r["isk"] for r in kills)
    lost = sum(r["isk"] for r in losses)
    return {
        "ships_destroyed": sum(1 for r in kills if not r["pod"]),
        "pods_destroyed": sum(1 for r in kills if r["pod"]),
        "ships_lost": sum(1 for r in losses if not r["pod"]),
        "pods_lost": sum(1 for r in losses if r["pod"]),
        "isk_destroyed": destroyed,
        "isk_lost": lost,
        "isk_pending": sum(1 for r in rows if r.get("pending")),
        "efficiency": (
            round(100 * destroyed / (destroyed + lost))
            if destroyed + lost
            else None
        ),
    }


def _name(names: dict, kind: str, key, fallback: str) -> str:
    if key is None:
        return fallback
    return (names.get(kind) or {}).get(str(key)) or fallback


def _hulls(rows: list[dict], names: dict) -> list[dict]:
    hulls: dict[Any, dict] = {}
    for row in rows:
        hull = hulls.setdefault(
            row["ship"],
            {
                "type_id": row["ship"],
                "name": _name(names, "ships", row["ship"], "Unknown ship"),
                "count": 0,
                "isk": 0,
            },
        )
        hull["count"] += 1
        hull["isk"] += row["isk"]
    return sorted(hulls.values(), key=lambda h: (-h["isk"], -h["count"]))


def _hostiles(rows: list[dict], names: dict) -> list[dict]:
    """Who we fought: pilots on our losses, and what we killed of theirs."""
    pilots: dict[int, set] = defaultdict(set)
    killed: Counter = Counter()
    isk: Counter = Counter()
    for row in rows:
        if row["outcome"] == OUTCOME_LOSS:
            for group, character in row.get("hostiles") or []:
                pilots[group or 0].add(character)
        elif not row["pod"]:
            killed[row.get("victim_group") or 0] += 1
            isk[row.get("victim_group") or 0] += row["isk"]
        else:
            isk[row.get("victim_group") or 0] += row["isk"]
    groups = set(pilots) | set(killed) | set(isk)
    result = [
        {
            "group_id": group or None,
            "name": _name(names, "groups", group or None, "No alliance"),
            "pilots": len(pilots.get(group, ())),
            "ships_killed": killed.get(group, 0),
            "isk_killed": isk.get(group, 0),
        }
        for group in groups
    ]
    return sorted(
        result,
        key=lambda g: (-g["pilots"], -g["isk_killed"], g["name"]),
    )


def _systems(rows: list[dict], names: dict) -> list[dict]:
    counts = Counter(row["system"] for row in rows)
    return [
        {
            "id": system,
            "name": _name(names, "systems", system, f"System {system}"),
            "mails": mails,
        }
        for system, mails in counts.most_common()
    ]


def _display_row(row: dict, names: dict) -> dict:
    return {
        "killmail_id": row["id"],
        "time": row["t"],
        "outcome": row["outcome"],
        "system_id": row["system"],
        "system_name": _name(
            names, "systems", row["system"], f"System {row['system']}"
        ),
        "ship_type_id": row["ship"],
        "ship_name": _name(names, "ships", row["ship"], "Unknown ship"),
        "victim_name": _name(names, "characters", row.get("victim"), ""),
        "group_name": _name(
            names, "groups", row.get("victim_group"), "No alliance"
        ),
        "isk": row["isk"],
        "pending": bool(row.get("pending")),
        "pod": bool(row["pod"]),
        "pilots": len(row.get("pilots") or ()),
    }


def _split_gaps(rows: list[dict]) -> list[dict]:
    gaps = []
    for index, (before, after) in enumerate(zip(rows, rows[1:])):
        start, end = parse_time(before["t"]), parse_time(after["t"])
        if end - start < SPLIT_MIN_GAP:
            continue
        head, tail = rows[: index + 1], rows[index + 1 :]
        gaps.append(
            {
                "at": after["t"],
                "after": before["t"],
                "seconds": int((end - start).total_seconds()),
                "before_kills": ship_count(head, OUTCOME_KILL),
                "before_losses": ship_count(head, OUTCOME_LOSS),
                "after_kills": ship_count(tail, OUTCOME_KILL),
                "after_losses": ship_count(tail, OUTCOME_LOSS),
            }
        )
    largest = sorted(gaps, key=lambda g: -g["seconds"])[:SPLIT_GAPS_SHOWN]
    return sorted(largest, key=lambda g: g["at"])


def zkill_related_url(
    systems: list[int],
    start: datetime,
    end: datetime,
    team: list[int],
) -> str:
    hour = start.replace(minute=0, second=0, microsecond=0)
    url = f"https://zkillboard.com/related/{systems[0]}/{hour:%Y%m%d%H}00/"
    options: dict[str, Any] = {}
    if team:
        options["A"] = team[:ZKILL_MAX_TEAM]
    if len(systems) > 1:
        options["systems"] = systems[:ZKILL_MAX_SYSTEMS]
    hours_after = math.ceil((end - hour).total_seconds() / 3600)
    if hours_after > ZKILL_HOURS_AFTER:
        options["hoursAfter"] = min(ZKILL_MAX_HOURS, hours_after)
    if options:
        encoded = quote(json.dumps(options, separators=(",", ":")), safe="")
        url += f"o/{encoded}/"
    return url


def brtools_related_url(system: int, start: datetime) -> str:
    return (
        f"https://br.evetools.org/related/{system}/"
        f"{start.replace(minute=0, second=0, microsecond=0):%Y%m%d%H}00"
    )


def battle_report_links(
    rows: list[dict], systems: list[dict], names: dict, battles: dict
) -> dict:
    """zKill related over every system and the rows' whole span, br.evetools
    for the busiest system (``systems`` come busiest first) at the first
    mail's hour, and the first eve-kill battle found. Used per round and,
    over all rows, for the whole fleet."""
    start, end = parse_time(rows[0]["t"]), parse_time(rows[-1]["t"])
    system_ids = [system["id"] for system in systems]
    links = {
        "zkillboard": zkill_related_url(
            system_ids, start, end, list(names.get("our_groups") or [])
        ),
        "brtools": brtools_related_url(system_ids[0], start),
        "evekill": None,
    }
    for row in rows:
        battle = battles.get(str(row["id"]))
        if battle:
            links["evekill"] = f"https://eve-kill.com/battle/{battle}"
            break
    return links


def _edit_flags(rows: list[dict], edits: list[dict]) -> dict:
    start, end = parse_time(rows[0]["t"]), parse_time(rows[-1]["t"])
    merges = [
        edit["id"]
        for edit in edits
        if edit["kind"] == "merge"
        and parse_time(edit["start"]) < end
        and parse_time(edit["end"]) > start
    ]
    splits = [
        edit["id"]
        for edit in edits
        if edit["kind"] == "split"
        and (
            parse_time(edit["start"]) == start
            or start < parse_time(edit["start"]) <= end
        )
    ]
    return {"merge_edit_ids": merges, "split_edit_ids": splits}


def summarize_segment(
    rows: list[dict],
    names: dict,
    *,
    number: int | None,
    edits: list[dict],
    battles: dict,
) -> dict:
    start, end = parse_time(rows[0]["t"]), parse_time(rows[-1]["t"])
    systems = _systems(rows, names)
    our_pilots = set()
    hostile_pilots = set()
    for row in rows:
        our_pilots.update(row.get("pilots") or ())
        hostile_pilots.update(c for _, c in row.get("hostiles") or ())
    biggest = sorted(rows, key=lambda r: -r["isk"])[:BIGGEST_SHOWN]
    return {
        "kind": "round" if number is not None else "skirmish",
        "number": number,
        "start": rows[0]["t"],
        "end": rows[-1]["t"],
        "minutes": max(1, round((end - start).total_seconds() / 60)),
        "systems": systems,
        **totals(rows),
        "mails": len(rows),
        "our_pilots": len(our_pilots),
        "hostile_pilots": len(hostile_pilots),
        "hostiles": _hostiles(rows, names),
        "hulls_killed": _hulls(
            [r for r in rows if r["outcome"] == OUTCOME_KILL], names
        ),
        "hulls_lost": _hulls(
            [r for r in rows if r["outcome"] == OUTCOME_LOSS], names
        ),
        "biggest": [_display_row(r, names) for r in biggest],
        "killmails": [_display_row(r, names) for r in rows],
        "links": battle_report_links(rows, systems, names, battles),
        "split_gaps": _split_gaps(rows),
        "fighting": False,
        **_edit_flags(rows, edits),
    }


def chart(rows: list[dict], start: datetime, end: datetime) -> dict[str, Any]:
    """Ships killed and lost per bin, from the fleet's start to its end."""
    minutes = max(1, math.ceil((end - start).total_seconds() / 60))
    bin_minutes = max(1, math.ceil(minutes / CHART_MAX_BINS))
    count = math.ceil(minutes / bin_minutes)
    bins = [[0, 0] for _ in range(count)]
    for row in rows:
        if row["pod"]:
            continue
        offset = (parse_time(row["t"]) - start).total_seconds() / 60
        index = min(count - 1, max(0, int(offset // bin_minutes)))
        bins[index][0 if row["outcome"] == OUTCOME_KILL else 1] += 1
    return {
        "start": _iso(start),
        "end": _iso(end),
        "bin_minutes": bin_minutes,
        "bins": bins,
    }


def build_payload(
    rows: list[dict],
    *,
    events: list[dict],
    names: dict,
    edits: list[dict],
    battles: dict,
    start: datetime,
    end: datetime | None,
    now: datetime,
) -> dict:
    """Everything the Fights tab and the desktop window draw."""
    segments = cut_segments(rows, events, edits)
    summaries = []
    number = 0
    for segment in segments:
        if is_round(segment):
            number += 1
            summaries.append(
                summarize_segment(
                    segment, names, number=number, edits=edits, battles=battles
                )
            )
        else:
            summaries.append(
                summarize_segment(
                    segment, names, number=None, edits=edits, battles=battles
                )
            )
    live = end is None
    if live and summaries:
        last = parse_time(summaries[-1]["end"])
        summaries[-1]["fighting"] = now - last <= FIGHTING_WITHIN
    chart_end = end or now
    if rows:
        chart_end = max(chart_end, parse_time(rows[-1]["t"]))
    return {
        "start": _iso(start),
        "end": _iso(end),
        "live": live,
        "totals": totals(rows),
        "round_count": number,
        "skirmish_count": len(summaries) - number,
        "rounds": summaries,
        "links": (
            battle_report_links(rows, _systems(rows, names), names, battles)
            if rows
            else None
        ),
        "events": events,
        "chart": chart(rows, start, chart_end),
        "edits": [
            {
                "id": edit["id"],
                "kind": edit["kind"],
                "start": _iso(parse_time(edit["start"])),
                "end": _iso(parse_time(edit["end"])) if edit["end"] else None,
                "created_by": edit.get("created_by"),
                "created_at": edit.get("created_at"),
            }
            for edit in edits
        ],
    }
