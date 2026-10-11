"""Fleet notification type definitions and renderers."""

from __future__ import annotations

from notifications.models import NotificationChannel
from notifications.registry import NotificationType, register

ROAM_REPORT_SITE = "https://www.roamreport.com"


def render_fleet_closed(ctx: dict) -> dict:
    fleet_id = ctx["fleet_id"]
    fleet_type = ctx.get("fleet_type") or "Fleet"
    location_name = ctx.get("location_name") or "Ask FC"
    objective = (ctx.get("objective") or "").strip()
    time_window = ctx.get("time_window") or ""
    member_count = int(ctx.get("member_count") or 0)
    aar_url = ctx.get("aar_url") or ""
    roam_report_url = (ctx.get("roam_report_url") or "").strip()

    title = f"Fleet {fleet_id} closed — AAR and roam report"
    header_lines = [
        f"Fleet {fleet_id}",
        f"{fleet_type} · {location_name}",
    ]
    if objective:
        header_lines.append(objective)
    if time_window:
        header_lines.append(time_window)
    header_lines.append(
        f"{member_count} {'pilot' if member_count == 1 else 'pilots'} tracked"
    )
    header = "\n".join(header_lines)

    if roam_report_url:
        roam_block = f"2) Roam report\n{roam_report_url}"
    else:
        roam_block = (
            "2) Roam report\n"
            "Could not generate automatically. Paste fleet members at:\n"
            f"{ROAM_REPORT_SITE}"
        )

    body = (
        f"Your fleet is closed.\n\n"
        f"{header}\n\n"
        f"Next steps:\n\n"
        f"1) Write your AAR\n"
        f"Post a thread in #aars:\n"
        f"{aar_url}\n\n"
        f"{roam_block}\n\n"
        f"o7\n"
        f"— BearThatCares"
    )
    return {
        "title": title,
        "body": title,
        "url": roam_report_url or aar_url,
        "discord_message": body,
        "subject": title,
        "eve_mail_body": body,
    }


FLEET_CLOSED = register(
    NotificationType(
        key="fleets.closed",
        feature="fleets",
        label="When my fleet closes",
        description=(
            "Send me an Eve mail with AAR and roam report links when I stop "
            "tracking a fleet."
        ),
        channels=(
            NotificationChannel.WEB,
            NotificationChannel.EVE_MAIL,
        ),
        defaults={
            NotificationChannel.WEB: True,
            NotificationChannel.EVE_MAIL: True,
        },
        render=render_fleet_closed,
        supports_topic_subscription=False,
    )
)
