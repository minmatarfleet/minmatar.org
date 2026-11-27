"""The daily roundup of a tribe group's coming fleets.

One silent Discord message listing the group's fleets in the next
``ROUNDUP_DAYS`` EVE days, starting tomorrow, grouped by day
(docs/tribes/group-fleet-roundup.md). ``tribes.tasks`` posts it.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from app.links import fleet_url
from fleets.endpoints.helpers import SILENT_MESSAGE_FLAG
from fleets.models import CAMPAIGN_FLEET_TYPES, EveFleet

ROUNDUP_DAYS = 5
DISCORD_MESSAGE_LIMIT = 2000
FOOTER = "-# Sign up on the fleet page."


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=timezone.utc)


def roundup_fleets(group, today: date) -> list[EveFleet]:
    """The group's fleets from tomorrow 00:00 EVE until the end of day 5,
    without cancelled, private or campaign (standing, gang) fleets."""
    start = _day_start(today + timedelta(days=1))
    end = _day_start(today + timedelta(days=ROUNDUP_DAYS + 1))
    return list(
        EveFleet.objects.filter(
            host_group=group, start_time__gte=start, start_time__lt=end
        )
        .exclude(status="cancelled")
        .exclude(invite_only=True)
        .exclude(type__in=CAMPAIGN_FLEET_TYPES)
        .select_related("doctrine", "created_by")
        .order_by("start_time", "id")
    )


def _day_heading(day: date, today: date) -> str:
    label = f"{day:%a} {day.day} {day:%b}"
    if day == today + timedelta(days=1):
        label = f"Tomorrow, {label}"
    return f"**{label}**\n"


def _line(fleet: EveFleet) -> str:
    # pylint: disable-next=import-outside-toplevel
    from fleets.tasks import get_fleet_emoji

    start = fleet.start_time.astimezone(timezone.utc)
    emoji = get_fleet_emoji(fleet.type)
    line = "- " + (f"{emoji} " if emoji else "")
    line += f"{start:%H:%M} EVE (<t:{int(start.timestamp())}:t>)"
    fc = fleet.fleet_commander
    if fc is not None:
        line += f" {fc.character_name}"
    title = fleet.objective or (fleet.doctrine.name if fleet.doctrine else "")
    if title:
        line += f" · {title}"
    return line + f" · [Fleet](<{fleet_url(fleet.id)}>)\n"


def build_roundup_payload(
    group, fleets: list[EveFleet], today: date
) -> dict | None:
    """The silent roundup message, or None when there are no fleets.

    Lines that would take it past Discord's 2000 characters become one
    "…and N more" line before the footer.
    """
    if not fleets:
        return None
    header = f"### {group.name} fleets — next {ROUNDUP_DAYS} days\n"
    budget = DISCORD_MESSAGE_LIMIT - len(header) - len(FOOTER)
    body = ""
    current_day = None
    for index, fleet in enumerate(fleets):
        day = fleet.start_time.astimezone(timezone.utc).date()
        chunk = _day_heading(day, today) if day != current_day else ""
        chunk += _line(fleet)
        left = len(fleets) - index - 1
        more = f"…and {left} more\n" if left else ""
        if len(body) + len(chunk) + len(more) > budget:
            body += f"…and {len(fleets) - index} more\n"
            break
        body += chunk
        current_day = day
    return {
        "content": header + body + FOOTER,
        "flags": SILENT_MESSAGE_FLAG,
        "allowed_mentions": {"parse": []},
    }
