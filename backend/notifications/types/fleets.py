"""Fleet notification type definitions and renderers."""

from __future__ import annotations

import html
import re

from feed.rollups.fleet_kills import format_isk
from notifications.models import NotificationChannel
from notifications.registry import NotificationType, register

REPORTS_LISTED = 5


# The Eve client renders a little HTML in mail: <b>, <br> and <a href>.
# Anything a player typed is escaped before it goes in.


def _text(value) -> str:
    return html.escape(str(value), quote=False)


def _link(url: str, label: str) -> str:
    # The href stays raw: the client may not decode &amp; in it. Our links
    # never hold quotes or brackets, but encode them so they can't break out.
    for char, code in (('"', "%22"), ("<", "%3C"), (">", "%3E")):
        url = url.replace(char, code)
    return f'<a href="{url}">{_text(label)}</a>'


def _plain(body: str) -> str:
    """The mail as plain text, links written out after their labels."""
    body = re.sub(r'<a href="([^"]*)">(.*?)</a>', r"\2 (\1)", body)
    body = body.replace("<br>", "\n")
    return html.unescape(re.sub(r"</?b>", "", body))


def _count(value: int, word: str, plural: str | None = None) -> str:
    return f"{value} {word if value == 1 else plural or word + 's'}"


def _isk(value) -> str:
    return f"{format_isk(int(value or 0))} ISK"


def _ships(ships: int, pods: int, isk) -> str:
    counts = _count(ships, "ship")
    if pods:
        counts += f", {_count(pods, 'pod')}"
    return f"{counts} · {_isk(isk)}"


def _mail(mail: dict | None) -> str:
    if not mail:
        return ""
    who = f" ({mail['victim_name']})" if mail.get("victim_name") else ""
    return _text(f"{mail['ship_name']}{who} · {_isk(mail['isk'])}")


def _header(ctx: dict) -> list[str]:
    title = f"Fleet {ctx['fleet_id']}"
    if objective := (ctx.get("objective") or "").strip():
        title += f" · {objective}"
    details = [
        ctx.get("fleet_type") or "Fleet",
        ctx.get("location_name") or "Ask FC",
    ]
    if doctrine := (ctx.get("doctrine_name") or "").strip():
        details.append(doctrine)
    lines = [f"<b>{_text(title)}</b>", _text(" · ".join(details))]
    if ctx.get("time_window"):
        when = ctx["time_window"]
        if ctx.get("duration"):
            when += f" · {ctx['duration']}"
        lines.append(_text(when))
    return lines


def _result(ctx: dict) -> list[str]:
    totals = ctx.get("totals") or {}
    ours = int(ctx.get("our_pilots") or 0)
    hostiles = int(ctx.get("hostile_pilots") or 0)
    pilots = f"Pilots: {ours} ours"
    if hostiles:
        pilots += f" vs {hostiles} hostile" + ("" if hostiles == 1 else "s")
    lines = ["<b>Result</b>"]

    destroyed = int(totals.get("ships_destroyed") or 0)
    lost = int(totals.get("ships_lost") or 0)
    pods_destroyed = int(totals.get("pods_destroyed") or 0)
    pods_lost = int(totals.get("pods_lost") or 0)
    if not destroyed + lost + pods_destroyed + pods_lost:
        return lines + [pilots, "No kills or losses on record."]

    lines.append(
        "Killed: "
        + _ships(destroyed, pods_destroyed, totals.get("isk_destroyed"))
    )
    lines.append("Lost: " + _ships(lost, pods_lost, totals.get("isk_lost")))
    if totals.get("efficiency") is not None:
        lines.append(f"Efficiency: {totals['efficiency']}%")
    lines.append(pilots)
    rounds = int(ctx.get("round_count") or 0)
    skirmishes = int(ctx.get("skirmish_count") or 0)
    if rounds or skirmishes:
        lines.append(
            f"Fights: {_count(rounds, 'round')}, "
            f"{_count(skirmishes, 'skirmish', 'skirmishes')}"
        )
    groups = ctx.get("hostile_groups") or []
    if groups:
        fought = ", ".join(
            (
                f"{group['name']} ({_count(group['pilots'], 'pilot')})"
                if group["pilots"]
                else group["name"]
            )
            for group in groups
        )
        lines.append(f"Fought: {_text(fought)}")
    if biggest := _mail(ctx.get("biggest_kill")):
        lines.append(f"Biggest kill: {biggest}")
    if biggest := _mail(ctx.get("biggest_loss")):
        lines.append(f"Biggest loss: {biggest}")
    return lines


def _battle_report(report: dict) -> str:
    label = "Round" if report.get("kind", "round") == "round" else "Skirmish"
    if report.get("number"):
        label += f" {report['number']}"
    parts = [
        f"{report['start']} EVE",
        ", ".join(report.get("systems") or []),
        f"{report['ships_destroyed']} killed, {report['ships_lost']} lost",
    ]
    if report.get("efficiency") is not None:
        parts.append(f"{report['efficiency']}%")
    details = " · ".join(part for part in parts if part)
    return f"{_link(report['url'], label)} · {_text(details)}"


def _reports(ctx: dict) -> list[str]:
    fleet_url = ctx.get("fleet_url") or ""
    lines = ["<b>Reports</b>"]
    if ctx.get("kill_report_url"):
        who = "open to anyone" if ctx.get("kill_report_public") else "members"
        lines.append(
            f"{_link(ctx['kill_report_url'], 'Kill report')}"
            f" · every kill and loss, {who}"
        )
    if ctx.get("battle_report_url"):
        lines.append(
            f"{_link(ctx['battle_report_url'], 'Battle report')}"
            " · the whole fleet, every side"
        )
    reports = ctx.get("battle_reports") or []
    lines.extend(
        f"› {_battle_report(report)}" for report in reports[:REPORTS_LISTED]
    )
    if len(reports) > REPORTS_LISTED:
        lines.append(
            f"{len(reports) - REPORTS_LISTED} more on the "
            f"{_link(f'{fleet_url}#aar', 'Fights tab')}"
        )
    elsewhere = [_link(f"{fleet_url}#aar", "Fights tab")] if fleet_url else []
    links = ctx.get("links") or {}
    for key, label in (
        ("zkillboard", "zKillboard"),
        ("brtools", "br.evetools"),
        ("evekill", "eve-kill"),
    ):
        if links.get(key):
            elsewhere.append(_link(links[key], label))
    if elsewhere:
        lines.append("Also: " + " · ".join(elsewhere))
    return lines


def _aar(ctx: dict) -> list[str]:
    line = f"Write it up in {_link(ctx.get('aar_url') or '', '#aars')}"
    if ctx.get("fleet_url"):
        line += (
            ", then add the link on the "
            f"{_link(ctx['fleet_url'] + '#aar', 'Fights tab')}"
        )
    return ["<b>Your AAR</b>", line + "."]


def render_fleet_closed(ctx: dict) -> dict:
    totals = ctx.get("totals") or {}
    title = f"Fleet {ctx['fleet_id']} report"
    destroyed = int(totals.get("ships_destroyed") or 0)
    lost = int(totals.get("ships_lost") or 0)
    if destroyed or lost:
        title += f" — {destroyed} killed, {lost} lost"
        if totals.get("efficiency") is not None:
            title += f", {totals['efficiency']}%"

    sections = [
        _header(ctx),
        _result(ctx),
        _reports(ctx),
        _aar(ctx),
        ["o7", "BearThatCares"],
    ]
    body = "<br><br>".join("<br>".join(lines) for lines in sections)
    return {
        "title": title,
        "body": title,
        "url": ctx.get("fleet_url") or ctx.get("aar_url") or "",
        "discord_message": _plain(body),
        "subject": title,
        "eve_mail_body": body,
    }


FLEET_CLOSED = register(
    NotificationType(
        key="fleets.closed",
        feature="fleets",
        label="When my fleet closes",
        description=(
            "Send me an Eve mail with my fleet's numbers, an AAR link and "
            "battle report links two hours after I stop tracking a fleet."
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
