"""Generate SQL to backfill EveFleet.aar_link from Discord #aars forum threads.

Reads fleet rows from production_readonly, crawls #aars threads via the Discord
bot API, matches threads to scheduled fleets, and prints UPDATE statements.

Usage (from backend/):
    pipenv run python scripts/generate_fleet_aar_link_sql.py

Output:
    scripts/output/fleet_aar_link_updates.sql
    scripts/output/fleet_aar_link_report.json
"""
from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, time, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import django
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

os_environ = __import__("os").environ
os_environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
django.setup()

from django.conf import settings
from django.utils import timezone as dj_timezone

from discord.models import DiscordUser
from fleets.models import EveFleet

logger = logging.getLogger(__name__)

AARS_FORUM_CHANNEL_ID = 1069380111897481256
BR_RE = re.compile(r"https://br\.evetools\.org/(?:br/)?([a-f0-9]+)", re.I)
TITLE_DATE_RE = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})")
MATCH_WINDOW_HOURS = 24
READ_DB = "production_readonly"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def _load_discord_token() -> str:
    token = os_environ.get("DISCORD_TOKEN")
    if token:
        return token
    env_candidates = [
        REPO_ROOT / "mcps" / ".env",
        Path("/root/minmatar.org/mcps/.env"),
    ]
    for env_path in env_candidates:
        if not env_path.is_file():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("DISCORD_TOKEN="):
                return line.split("=", 1)[1].strip()
    return settings.DISCORD_BOT_TOKEN


def _discord_session(token: str) -> requests.Session:
    session = requests.Session()
    retry = Retry(total=5, status_forcelist=[429, 500, 502, 503, 504], backoff_factor=1)
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"Authorization": f"Bot {token}"})
    return session


@dataclass
class AarThread:
    thread_id: int
    name: str
    owner_id: int | None
    created_at: datetime
    inferred_at: datetime
    content: str
    br_ids: list[str]
    aar_url: str


@dataclass
class FleetMatch:
    fleet_id: int
    fleet_start: str
    fleet_description: str
    thread_id: int
    thread_name: str
    thread_inferred_at: str
    aar_url: str
    br_ids: list[str]
    match_delta_minutes: float
    match_reason: str


def _parse_iso(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts).astimezone(timezone.utc)


def _thread_inferred_at(thread: dict, content: str) -> datetime:
    name = thread.get("name") or ""
    match = TITLE_DATE_RE.search(name)
    if match:
        date = datetime.strptime(match.group("date"), "%Y-%m-%d").date()
        return datetime.combine(date, time(12, 0), tzinfo=timezone.utc)
    return _parse_iso(thread["thread_metadata"]["create_timestamp"])


def _discord_get_json(
    session: requests.Session, url: str, params: dict | None = None
) -> dict:
    response = session.get(url, params=params or {}, timeout=30)
    response.raise_for_status()
    return response.json()


def _fetch_forum_threads(session: requests.Session, channel_id: int) -> list[dict]:
    base = f"https://discord.com/api/v10/channels/{channel_id}/threads"
    threads: dict[int, dict] = {}

    try:
        active = _discord_get_json(session, f"{base}/active")
        for thread in active.get("threads", []):
            threads[int(thread["id"])] = thread
    except requests.HTTPError as exc:
        logger.warning("Could not list active forum threads: %s", exc)

    before: str | None = None
    while True:
        params: dict[str, str | int] = {"limit": 100}
        if before:
            params["before"] = before
        page = _discord_get_json(session, f"{base}/archived/public", params=params)
        batch = page.get("threads", [])
        if not batch:
            break
        for thread in batch:
            threads[int(thread["id"])] = thread
        if not page.get("has_more"):
            break
        before = batch[-1]["thread_metadata"]["archive_timestamp"]

    return list(threads.values())


def _fetch_thread_starter_content(
    session: requests.Session, forum_channel_id: int, thread_id: int
) -> str:
    # Forum starter message id equals thread id.
    try:
        message = _discord_get_json(
            session,
            f"https://discord.com/api/v10/channels/{forum_channel_id}/messages/{thread_id}",
        )
        return message.get("content") or ""
    except requests.HTTPError:
        pass

    messages = _discord_get_json(
        session,
        f"https://discord.com/api/v10/channels/{thread_id}/messages",
        params={"limit": 100},
    )
    if not messages:
        return ""
    starter = min(messages, key=lambda m: int(m["id"]))
    return starter.get("content") or ""


def _collect_aar_threads(
    session: requests.Session,
    *,
    period_start: datetime,
    period_end: datetime,
) -> list[AarThread]:
    guild_id = settings.DISCORD_GUILD_ID
    threads: list[AarThread] = []

    for index, raw in enumerate(_fetch_forum_threads(session, AARS_FORUM_CHANNEL_ID), start=1):
        if index % 50 == 0:
            logger.info("Scanning forum threads... %s", index)

        inferred = _thread_inferred_at(raw, "")
        if inferred < period_start or inferred >= period_end:
            continue

        thread_id = int(raw["id"])
        content = _fetch_thread_starter_content(
            session, AARS_FORUM_CHANNEL_ID, thread_id
        )
        inferred = _thread_inferred_at(raw, content)
        if inferred < period_start or inferred >= period_end:
            continue

        owner_id = raw.get("owner_id")
        threads.append(
            AarThread(
                thread_id=thread_id,
                name=raw.get("name") or "",
                owner_id=int(owner_id) if owner_id else None,
                created_at=_parse_iso(raw["thread_metadata"]["create_timestamp"]),
                inferred_at=inferred,
                content=content,
                br_ids=BR_RE.findall(content),
                aar_url=f"https://discord.com/channels/{guild_id}/{thread_id}",
            )
        )

    threads.sort(key=lambda t: t.inferred_at)
    return threads


def _load_discord_user_map() -> dict[int, int]:
    return {
        int(row["id"]): int(row["user_id"])
        for row in DiscordUser.objects.using(READ_DB).values("id", "user_id")
    }


def _load_fleets(period_start: datetime, period_end: datetime) -> list[EveFleet]:
    return list(
        EveFleet.objects.using(READ_DB)
        .filter(start_time__gte=period_start, start_time__lt=period_end)
        .order_by("start_time")
    )


def _match_fleets(
    threads: list[AarThread],
    fleets: list[EveFleet],
    discord_users: dict[int, int],
) -> tuple[list[FleetMatch], list[dict], list[dict]]:
    matches: list[FleetMatch] = []
    unmatched_threads: list[dict] = []
    used_fleet_ids: set[int] = set()

    window = MATCH_WINDOW_HOURS * 3600

    for thread in threads:
        owner_user_id = (
            discord_users.get(thread.owner_id) if thread.owner_id else None
        )
        candidates: list[tuple[float, EveFleet, str]] = []

        for fleet in fleets:
            if fleet.id in used_fleet_ids:
                continue
            if fleet.aar_link:
                continue
            delta = abs((fleet.start_time - thread.inferred_at).total_seconds())
            if delta > window:
                continue
            if owner_user_id and fleet.created_by_id != owner_user_id:
                continue
            reason = "owner+time" if owner_user_id else "time-only"
            candidates.append((delta, fleet, reason))

        if not candidates:
            unmatched_threads.append(
                {
                    "thread_id": thread.thread_id,
                    "thread_name": thread.name,
                    "inferred_at": thread.inferred_at.isoformat(),
                    "owner_id": thread.owner_id,
                    "owner_user_id": owner_user_id,
                    "br_ids": thread.br_ids,
                    "aar_url": thread.aar_url,
                }
            )
            continue

        delta, fleet, reason = min(candidates, key=lambda item: item[0])
        used_fleet_ids.add(fleet.id)
        matches.append(
            FleetMatch(
                fleet_id=fleet.id,
                fleet_start=fleet.start_time.isoformat(),
                fleet_description=(fleet.description or "")[:160],
                thread_id=thread.thread_id,
                thread_name=thread.name,
                thread_inferred_at=thread.inferred_at.isoformat(),
                aar_url=thread.aar_url,
                br_ids=thread.br_ids,
                match_delta_minutes=round(delta / 60, 1),
                match_reason=reason,
            )
        )

    matched_fleet_ids = {m.fleet_id for m in matches}
    unmatched_fleets = [
        {
            "fleet_id": fleet.id,
            "start_time": fleet.start_time.isoformat(),
            "created_by_id": fleet.created_by_id,
            "description": (fleet.description or "")[:160],
        }
        for fleet in fleets
        if fleet.id not in matched_fleet_ids and not fleet.aar_link
    ]

    return matches, unmatched_threads, unmatched_fleets


def _sql_escape(value: str) -> str:
    return value.replace("'", "''")


def _render_sql(matches: list[FleetMatch]) -> str:
    lines = [
        "-- Backfill EveFleet.aar_link from Discord #aars forum threads",
        f"-- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"-- Matches: {len(matches)}",
        "START TRANSACTION;",
        "",
    ]

    for match in matches:
        lines.extend(
            [
                f"-- fleet_id={match.fleet_id} start={match.fleet_start}",
                f"-- thread: {match.thread_name!r} ({match.thread_id})",
                f"-- delta_minutes={match.match_delta_minutes} reason={match.match_reason}",
                (
                    "UPDATE fleets_evefleet "
                    f"SET aar_link = '{_sql_escape(match.aar_url)}' "
                    f"WHERE id = {match.fleet_id} AND (aar_link IS NULL OR aar_link = '');"
                ),
                "",
            ]
        )

    lines.append("COMMIT;")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    period_start = dj_timezone.make_aware(datetime(2024, 1, 1))
    period_end = dj_timezone.make_aware(datetime(2024, 11, 1))

    client = _discord_session(_load_discord_token())
    logger.info("Fetching #aars forum threads from Discord...")
    threads = _collect_aar_threads(
        client, period_start=period_start, period_end=period_end
    )
    logger.info("Threads in campaign window: %s", len(threads))

    discord_users = _load_discord_user_map()
    fleets = _load_fleets(period_start, period_end)
    logger.info("Scheduled fleets in window: %s", len(fleets))

    matches, unmatched_threads, unmatched_fleets = _match_fleets(
        threads, fleets, discord_users
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sql_path = OUTPUT_DIR / "fleet_aar_link_updates.sql"
    report_path = OUTPUT_DIR / "fleet_aar_link_report.json"

    sql_path.write_text(_render_sql(matches), encoding="utf-8")
    report_path.write_text(
        json.dumps(
            {
                "period": {
                    "start": period_start.isoformat(),
                    "end": period_end.isoformat(),
                },
                "summary": {
                    "threads": len(threads),
                    "fleets": len(fleets),
                    "matches": len(matches),
                    "unmatched_threads": len(unmatched_threads),
                    "unmatched_fleets": len(unmatched_fleets),
                },
                "matches": [asdict(m) for m in matches],
                "unmatched_threads": unmatched_threads,
                "unmatched_fleets": unmatched_fleets[:200],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    logger.info("Wrote %s", sql_path)
    logger.info("Wrote %s", report_path)
    logger.info(
        "Matched %s fleets; %s threads unmatched; %s fleets still without links",
        len(matches),
        len(unmatched_threads),
        len(unmatched_fleets),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
