"""Create a roamreport.com report when a tracked fleet closes."""

from __future__ import annotations

import logging
from datetime import datetime, timezone as dt_timezone

import requests
from django.conf import settings
from django.utils import timezone

from fleets.models import EveFleet, EveFleetInstance, EveFleetInstanceMember
from notifications.service import notify_user
from notifications.types.fleets import FLEET_CLOSED

logger = logging.getLogger(__name__)

ROAM_REPORT_SITE = "https://www.roamreport.com"
DEFAULT_API_URL = f"{ROAM_REPORT_SITE}/api/fleets"
REQUEST_TIMEOUT_SECONDS = 30

# Discord #aars forum. Settings win; this is the fallback for deployments
# whose settings.py predates DISCORD_AARS_FORUM_CHANNEL_ID.
DEFAULT_AARS_FORUM_CHANNEL_ID = 1069380111897481256


def schedule_roam_report(fleet_id: int) -> None:
    # Imported lazily: fleets.tasks imports this module.
    from fleets.tasks import (  # pylint: disable=import-outside-toplevel
        publish_fleet_roam_report,
    )

    publish_fleet_roam_report.delay(fleet_id)


def isoformat_utc(value: datetime) -> str:
    if timezone.is_naive(value):
        value = timezone.make_aware(value, dt_timezone.utc)
    return value.astimezone(dt_timezone.utc).replace(microsecond=0).isoformat()


def format_eve_window(start: datetime, end: datetime) -> str:
    if timezone.is_naive(start):
        start = timezone.make_aware(start, dt_timezone.utc)
    if timezone.is_naive(end):
        end = timezone.make_aware(end, dt_timezone.utc)
    start_utc = start.astimezone(dt_timezone.utc)
    end_utc = end.astimezone(dt_timezone.utc)
    if start_utc.date() == end_utc.date():
        return (
            f"{start_utc.strftime('%Y-%m-%d %H:%M')}–"
            f"{end_utc.strftime('%H:%M')} EVE"
        )
    return (
        f"{start_utc.strftime('%Y-%m-%d %H:%M')} – "
        f"{end_utc.strftime('%Y-%m-%d %H:%M')} EVE"
    )


def fleet_report_window(fleet: EveFleet) -> tuple[datetime, datetime] | None:
    instances = list(EveFleetInstance.objects.filter(eve_fleet=fleet))
    if not instances:
        return None
    starts = [fleet.start_time]
    starts.extend(
        instance.start_time for instance in instances if instance.start_time
    )
    ends = [instance.end_time for instance in instances if instance.end_time]
    if not ends:
        ends = [timezone.now()]
    return min(starts), max(ends)


def fleet_member_names(fleet: EveFleet) -> list[str]:
    names = (
        EveFleetInstanceMember.objects.filter(
            eve_fleet_instance__eve_fleet=fleet
        )
        .exclude(character_name="")
        .values_list("character_name", flat=True)
        .distinct()
    )
    return sorted(set(names))


def parse_roam_report_url(response: requests.Response) -> str | None:
    location = response.headers.get("Location") or response.headers.get(
        "location"
    )
    if location and location.startswith("http"):
        return location.rstrip("/")

    data = None
    try:
        data = response.json()
    except ValueError:
        data = None

    if isinstance(data, dict):
        for key in ("url", "report_url", "href"):
            value = data.get(key)
            if value:
                return str(value)
        report_id = data.get("id")
        if report_id:
            return f"{ROAM_REPORT_SITE}/f/{report_id}"

    text = (response.text or "").strip()
    if text.startswith("http"):
        return text.split()[0]
    return None


def create_roam_report(
    *, start: datetime, end: datetime, members: list[str]
) -> str | None:
    api_key = getattr(settings, "ROAM_REPORT_API_KEY", "") or ""
    if not api_key:
        logger.info("Skipping roam report POST: ROAM_REPORT_API_KEY is empty")
        return None
    if not members:
        logger.info("Skipping roam report POST: no fleet members")
        return None

    api_url = getattr(settings, "ROAM_REPORT_API_URL", "") or DEFAULT_API_URL
    payload = {
        "start": isoformat_utc(start),
        "end": isoformat_utc(end),
        "members": members,
    }
    response = requests.post(
        api_url,
        json=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if not response.ok:
        logger.warning(
            "Roam report POST failed: %s %s",
            response.status_code,
            response.text[:500],
        )
        return None
    url = parse_roam_report_url(response)
    if not url:
        logger.warning("Roam report POST succeeded but no URL in response")
    return url


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


def publish_fleet_roam_report_impl(fleet_id: int) -> str | None:
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        logger.warning("Roam report skipped: fleet %s not found", fleet_id)
        return None
    if fleet.status != "complete":
        logger.info(
            "Roam report skipped: fleet %s status is %s",
            fleet_id,
            fleet.status,
        )
        return None

    window = fleet_report_window(fleet)
    if window is None:
        logger.info(
            "Roam report skipped: fleet %s has no tracking instance", fleet_id
        )
        return None

    start, end = window
    members = fleet_member_names(fleet)
    if not members:
        logger.info(
            "Roam report skipped: fleet %s tracked no members", fleet_id
        )
        return None

    report_url = fleet.roam_report_url or None
    if not report_url:
        try:
            report_url = create_roam_report(
                start=start, end=end, members=members
            )
        except requests.RequestException:
            logger.warning(
                "Roam report request failed for fleet %s",
                fleet_id,
                exc_info=True,
            )
            report_url = None
        if report_url:
            fleet.roam_report_url = report_url
            fleet.save(update_fields=["roam_report_url"])

    _notify_fleet_closed(fleet, start, end, members, report_url)
    return report_url


def _notify_fleet_closed(
    fleet: EveFleet,
    start: datetime,
    end: datetime,
    members: list[str],
    report_url: str | None,
) -> None:
    if not fleet.created_by:
        logger.info(
            "Skipping fleet close mail: fleet %s has no owner", fleet.id
        )
        return
    location = (
        fleet.formup_location.location_name
        if fleet.formup_location
        else "Ask FC"
    )
    notify_user(
        fleet.created_by,
        FLEET_CLOSED.key,
        {
            "fleet_id": fleet.id,
            "fleet_type": fleet.get_type_display(),
            "location_name": location,
            "objective": (fleet.objective or "").strip(),
            "time_window": format_eve_window(start, end),
            "member_count": len(members),
            "aar_url": aars_forum_url(),
            "roam_report_url": report_url or "",
        },
        idempotency_key=f"fleets.closed:{fleet.id}",
    )
