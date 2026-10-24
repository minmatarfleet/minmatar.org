"""Mail the FC their fleet's numbers once its fight timeline settles.

The timeline settles two hours after tracking ends, after the zKillboard
sweep has filled in mails the live feed missed, so the numbers in the mail
are the ones the Fights tab keeps. Only the tick's settle task sends it, so
backfilling old fleets never mails anyone.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from urllib.parse import urlencode

from django.conf import settings
from django.utils import timezone

from app.links import fleet_url, site_url
from fleets.helpers.fights.rounds import (
    OUTCOME_KILL,
    OUTCOME_LOSS,
    hostile_groups,
    parse_time,
)
from fleets.helpers.fights.serve import pilot_numbers
from fleets.helpers.visibility import public_kills_allowed
from fleets.models import EveFleetInstance
from notifications.service import notify_user
from notifications.types.fleets import FLEET_CLOSED

logger = logging.getLogger(__name__)

# Discord #aars forum. Settings win; this is the fallback for deployments
# whose settings.py predates DISCORD_AARS_FORUM_CHANNEL_ID.
DEFAULT_AARS_FORUM_CHANNEL_ID = 1069380111897481256

HOSTILE_GROUPS_LISTED = 3
# The Fights tab opens an engagement's report a minute either side of it.
REPORT_WINDOW_PAD = timedelta(minutes=1)


def aars_forum_url() -> str:
    channel_id = getattr(
        settings,
        "DISCORD_AARS_FORUM_CHANNEL_ID",
        DEFAULT_AARS_FORUM_CHANNEL_ID,
    )
    return (
        f"https://discord.com/channels/{settings.DISCORD_GUILD_ID}"
        f"/{channel_id}"
    )


def _utc(value: datetime) -> datetime:
    if timezone.is_naive(value):
        value = timezone.make_aware(value, dt_timezone.utc)
    return value.astimezone(dt_timezone.utc)


def format_eve_window(start: datetime, end: datetime) -> str:
    start_utc, end_utc = _utc(start), _utc(end)
    if start_utc.date() == end_utc.date():
        return (
            f"{start_utc.strftime('%Y-%m-%d %H:%M')}–"
            f"{end_utc.strftime('%H:%M')} EVE"
        )
    return (
        f"{start_utc.strftime('%Y-%m-%d %H:%M')} – "
        f"{end_utc.strftime('%Y-%m-%d %H:%M')} EVE"
    )


def format_duration(start: datetime, end: datetime) -> str:
    minutes = max(0, round((end - start).total_seconds() / 60))
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


def tracked_window(fleet) -> tuple[datetime, datetime] | None:
    """First tracked start to last end, once every instance has ended."""
    spans = list(
        EveFleetInstance.objects.filter(eve_fleet=fleet).values_list(
            "start_time", "end_time"
        )
    )
    if not spans or any(end is None for _, end in spans):
        return None
    starts = [start for start, _ in spans if start] or [fleet.start_time]
    return min(starts), max(end for _, end in spans)


def _name(names: dict, kind: str, key, fallback: str = "") -> str:
    if key is None:
        return fallback
    return (names.get(kind) or {}).get(str(key)) or fallback


def _biggest(rows: list[dict], names: dict, outcome: str) -> dict | None:
    matching = [row for row in rows if row["outcome"] == outcome]
    if not matching:
        return None
    row = max(matching, key=lambda r: r["isk"])
    return {
        "ship_name": _name(names, "ships", row["ship"], "Unknown ship"),
        "victim_name": _name(names, "characters", row.get("victim")),
        "isk": row["isk"],
    }


def _iso(moment: datetime) -> str:
    return moment.astimezone(dt_timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"
    )


def _window_url(report_url: str, summary: dict) -> str:
    """The battle report scoped to one engagement, as the Fights tab links
    it. A window, unlike a round number, survives the FC re-cutting rounds.
    """
    start = parse_time(summary["start"]) - REPORT_WINDOW_PAD
    end = parse_time(summary["end"]) + REPORT_WINDOW_PAD
    return (
        f"{report_url}?{urlencode({'start': _iso(start), 'end': _iso(end)})}"
    )


def _battle_reports(report_url: str, summaries: list[dict]) -> list[dict]:
    """Each round's slice of the battle report; skirmishes only when there
    was no round."""
    kind = (
        "round"
        if any(summary["kind"] == "round" for summary in summaries)
        else "skirmish"
    )
    reports = []
    for summary in summaries:
        if summary["kind"] != kind:
            continue
        reports.append(
            {
                "kind": kind,
                "number": summary["number"],
                "start": parse_time(summary["start"]).strftime("%H:%M"),
                "minutes": summary["minutes"],
                "systems": [s["name"] for s in summary["systems"][:2]],
                "ships_destroyed": summary["ships_destroyed"],
                "ships_lost": summary["ships_lost"],
                "efficiency": summary["efficiency"],
                "url": _window_url(report_url, summary),
            }
        )
    return reports


def _kill_report_url(fleet, page: str) -> str:
    """The public kills page, or the Kills tab when the fleet is private."""
    if public_kills_allowed(fleet):
        return site_url(f"/fleets/{fleet.id}/kills")
    return f"{page}#kills"


def report_context(fleet, timeline, start: datetime, end: datetime) -> dict:
    payload = timeline.payload or {}
    rows = timeline.killmails or []
    names = timeline.names or {}
    totals = payload.get("totals") or {}
    numbers = pilot_numbers(fleet, rows)
    has_mails = bool(rows)
    page = fleet_url(fleet.id, ended=True)
    report_url = f"{page}/report"
    return {
        "fleet_id": fleet.id,
        "fleet_type": fleet.get_type_display(),
        "location_name": (
            fleet.formup_location.location_name
            if fleet.formup_location
            else "Ask FC"
        ),
        "objective": (fleet.objective or "").strip(),
        "doctrine_name": fleet.doctrine.name if fleet.doctrine else "",
        "time_window": format_eve_window(start, end),
        "duration": format_duration(start, end),
        "our_pilots": numbers["our_pilots"] or 0,
        "hostile_pilots": numbers["hostile_pilots"] or 0,
        "totals": totals,
        "round_count": payload.get("round_count") or 0,
        "skirmish_count": payload.get("skirmish_count") or 0,
        "battle_report_url": report_url if has_mails else "",
        "battle_reports": _battle_reports(
            report_url, payload.get("rounds") or []
        ),
        "biggest_kill": _biggest(rows, names, OUTCOME_KILL),
        "biggest_loss": _biggest(rows, names, OUTCOME_LOSS),
        "hostile_groups": [
            {"name": group["name"], "pilots": group["pilots"]}
            for group in hostile_groups(rows, names)
            if group["group_id"]
        ][:HOSTILE_GROUPS_LISTED],
        "fleet_url": page,
        "kill_report_url": _kill_report_url(fleet, page) if has_mails else "",
        "kill_report_public": has_mails and public_kills_allowed(fleet),
        "links": (payload.get("links") or {}) if has_mails else {},
        "aar_url": aars_forum_url(),
    }


def send_fleet_report(fleet, timeline) -> bool:
    """Mail the FC once the fleet's timeline has settled."""
    if fleet.status != "complete":
        logger.info(
            "Fleet report skipped: fleet %s status is %s",
            fleet.id,
            fleet.status,
        )
        return False
    if not fleet.created_by:
        logger.info("Fleet report skipped: fleet %s has no owner", fleet.id)
        return False
    window = tracked_window(fleet)
    if window is None:
        logger.info("Fleet report skipped: fleet %s is not closed", fleet.id)
        return False
    context = report_context(fleet, timeline, *window)
    if not context["our_pilots"]:
        # Nobody tracked: nothing to report and nobody to thank.
        logger.info("Fleet report skipped: fleet %s tracked nobody", fleet.id)
        return False
    notify_user(
        fleet.created_by,
        FLEET_CLOSED.key,
        context,
        idempotency_key=f"fleets.closed:{fleet.id}:report",
    )
    return True
