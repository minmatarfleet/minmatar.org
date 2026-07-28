"""Industry order notification type definitions and renderers."""

from __future__ import annotations

from django.conf import settings

from notifications.models import NotificationChannel
from notifications.registry import NotificationType, register

_ROLE_LABELS = {
    "blueprint": "blueprints",
    "minerals": "minerals",
    "PI": "planetary stuff",
}


def _web_base() -> str:
    return getattr(settings, "WEB_LINK_URL", "https://my.minmatar.org").rstrip(
        "/"
    )


def _order_url(order_id: int) -> str:
    return f"{_web_base()}/industry/orders/{order_id}/"


def _contract_url(order_id: int, item_id: int, assignment_id: int) -> str:
    return (
        f"{_web_base()}/industry/orders/contract"
        f"?order_id={order_id}&item_id={item_id}&assignment_id={assignment_id}"
    )


def _format_needed_by(needed_by: str) -> str:
    """Prefer a short date like Aug 1 if ISO date is passed."""
    if not needed_by:
        return ""
    try:
        parts = needed_by[:10].split("-")
        month = int(parts[1])
        day = int(parts[2])
        months = (
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        )
        return f"{months[month - 1]} {day}"
    except (ValueError, IndexError):
        return needed_by


def _help_lines(coordinators: list) -> list[str]:
    lines = []
    for c in coordinators:
        role = _ROLE_LABELS.get(c.get("role") or "", c.get("role") or "help")
        name = c.get("character_name") or "someone"
        lines.append(f"- {name} (can help with {role})")
    return lines


def render_order_created(ctx: dict) -> dict:
    order_id = ctx["order_id"]
    short = ctx.get("public_short_code") or str(order_id)
    needed = _format_needed_by(ctx.get("needed_by") or "")
    items = ctx.get("items_summary") or ""
    location = ctx.get("location_name") or ""
    url = _order_url(order_id)

    title = f"New build order ({short})"
    bits = []
    if needed:
        bits.append(f"due {needed}")
    if location:
        bits.append(location)
    if items:
        bits.append(items)
    detail = " · ".join(bits) if bits else "Open it if you want a piece."
    body = f"{detail}. Open the order to claim what you can build."

    discord = (
        f"**New build order ({short})**\n"
        f"{detail}\n\n"
        f"Want in? Open the order and grab a piece:\n{url}"
    )
    eve_body = (
        f"Hey — there's a new build order ({short}).\n\n"
        f"{detail}\n\n"
        f"If you've got time, open it and claim something to build:\n{url}\n\n"
        f"— Bear"
    )
    return {
        "title": title,
        "body": body,
        "url": url,
        "discord_message": discord,
        "subject": title,
        "eve_mail_body": eve_body,
    }


def render_order_assignment(ctx: dict) -> dict:
    order_id = ctx["order_id"]
    short = ctx.get("public_short_code") or str(order_id)
    item_name = ctx.get("item_name") or "that ship"
    quantity = ctx.get("quantity") or ""
    assignment_id = ctx["assignment_id"]
    item_id = ctx["item_id"]
    delivery_url = _contract_url(order_id, item_id, assignment_id)
    help_lines = _help_lines(ctx.get("coordinators") or [])
    help_block = (
        "\n".join(help_lines)
        if help_lines
        else "- Nobody signed up to help yet — ask in industry chat if you're stuck."
    )
    qty_bit = f"{quantity}× " if quantity != "" else ""

    title = f"You're building {qty_bit}{item_name}"
    body = (
        f"Order {short}. Stuck for blueprints or minerals? Ping the folks below. "
        f"When you're done, tap here to hand it in."
    )
    discord = (
        f"**You're on it — {qty_bit}{item_name}** (order {short})\n\n"
        f"**Who can help**\n{help_block}\n\n"
        f"When you're finished, hand it in here:\n{delivery_url}"
    )
    eve_body = (
        f"You're down for {qty_bit}{item_name} on order {short}. Nice.\n\n"
        f"Need blueprints, minerals, or PI? Try these folks:\n{help_block}\n\n"
        f"When the build is done, hand it in here so we can mark you complete:\n"
        f"{delivery_url}\n\n"
        f"— Bear"
    )
    return {
        "title": title,
        "body": body,
        "url": delivery_url,
        "discord_message": discord,
        "subject": title,
        "eve_mail_body": eve_body,
    }


def render_order_job(ctx: dict) -> dict:
    order_id = ctx["order_id"]
    short = ctx.get("public_short_code") or str(order_id)
    item_name = ctx.get("item_name") or "your build"
    assignment_id = ctx["assignment_id"]
    item_id = ctx["item_id"]
    delivery_url = _contract_url(order_id, item_id, assignment_id)

    title = f"{item_name} is cooking"
    body = (
        f"We saw your build start for order {short}. "
        f"When it finishes, hand it in so we know you're done."
    )
    discord = (
        f"**{item_name} is cooking** (order {short})\n\n"
        f"When it finishes, hand it in here:\n{delivery_url}"
    )
    eve_body = (
        f"Looks like your {item_name} build for order {short} is running.\n\n"
        f"When it's done, hand it in here — takes a minute:\n{delivery_url}\n\n"
        f"— Bear"
    )
    return {
        "title": title,
        "body": body,
        "url": delivery_url,
        "discord_message": discord,
        "subject": title,
        "eve_mail_body": eve_body,
    }


ORDER_CREATED = register(
    NotificationType(
        key="industry.order.created",
        feature="industry",
        label="New build orders",
        description="Ping me when there's a new order I might want to build for.",
        channels=(
            NotificationChannel.WEB,
            NotificationChannel.DISCORD,
            NotificationChannel.EVE_MAIL,
        ),
        defaults={
            NotificationChannel.WEB: True,
            NotificationChannel.DISCORD: False,
            NotificationChannel.EVE_MAIL: False,
        },
        render=render_order_created,
        supports_topic_subscription=True,
    )
)

ORDER_ASSIGNMENT = register(
    NotificationType(
        key="industry.order.assignment",
        feature="industry",
        label="After I claim a build",
        description=(
            "Send me who can help (blueprints/minerals) and the hand-in link "
            "when I claim something."
        ),
        channels=(
            NotificationChannel.WEB,
            NotificationChannel.DISCORD,
            NotificationChannel.EVE_MAIL,
        ),
        defaults={
            NotificationChannel.WEB: True,
            NotificationChannel.DISCORD: True,
            NotificationChannel.EVE_MAIL: False,
        },
        render=render_order_assignment,
        supports_topic_subscription=False,
    )
)

ORDER_JOB = register(
    NotificationType(
        key="industry.order.job",
        feature="industry",
        label="When my build starts",
        description=(
            "Nudge me with the hand-in link once my manufacturing job is going."
        ),
        channels=(
            NotificationChannel.WEB,
            NotificationChannel.DISCORD,
            NotificationChannel.EVE_MAIL,
        ),
        defaults={
            NotificationChannel.WEB: True,
            NotificationChannel.DISCORD: True,
            NotificationChannel.EVE_MAIL: False,
        },
        render=render_order_job,
        supports_topic_subscription=False,
    )
)
