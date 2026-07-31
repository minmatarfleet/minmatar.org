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

# Keep Discord embeds / Eve mail / web push under size limits.
_MAX_ITEM_LINES = 8


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


def _help_lines(coordinators: list) -> list[str]:
    lines = []
    for c in coordinators:
        role = _ROLE_LABELS.get(c.get("role") or "", c.get("role") or "help")
        name = c.get("character_name") or "someone"
        lines.append(f"- {name} (can help with {role})")
    return lines


def _item_lines(ctx: dict) -> list[str]:
    """Normalize item lines from `items` list or legacy `items_summary` string."""
    items = ctx.get("items")
    if isinstance(items, list) and items:
        return [str(line) for line in items if line]
    summary = (ctx.get("items_summary") or "").strip()
    if not summary:
        return []
    return [part.strip() for part in summary.split(",") if part.strip()]


def _capped_item_lines(lines: list[str]) -> list[str]:
    if len(lines) <= _MAX_ITEM_LINES:
        return lines
    remaining = len(lines) - _MAX_ITEM_LINES
    return lines[:_MAX_ITEM_LINES] + [f"…and {remaining} more"]


def _bullet_block(lines: list[str], *, empty: str = "- (see order)") -> str:
    capped = _capped_item_lines(lines)
    if not capped:
        return empty
    return "\n".join(f"- {line}" for line in capped)


def _body_item_phrase(lines: list[str]) -> str:
    capped = _capped_item_lines(lines)
    return ", ".join(capped)


def render_order_created(ctx: dict) -> dict:
    order_id = ctx["order_id"]
    short = ctx.get("public_short_code") or str(order_id)
    url = _order_url(order_id)
    lines = _item_lines(ctx)
    bullets = _bullet_block(lines)

    title = f"New Build Order {short}"
    phrase = _body_item_phrase(lines)
    body = (
        f"{phrase}. Want in? Open the order."
        if phrase
        else "Want in? Open the order."
    )

    discord = (
        f"## New Build Order `{short}`\n"
        f"{bullets}\n\n"
        f"Want in? [Click here]({url})"
    )
    eve_body = (
        f"New Build Order {short}\n\n"
        f"{bullets}\n\n"
        f"Want in? {url}\n\n"
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
    item_name = ctx.get("item_name") or "that ship"
    quantity = ctx.get("quantity") or ""
    assignment_id = ctx["assignment_id"]
    item_id = ctx["item_id"]
    delivery_url = _contract_url(order_id, item_id, assignment_id)

    items = ctx.get("items")
    if isinstance(items, list) and items:
        item_lines = [str(line) for line in items if line]
    else:
        qty_bit = f"{quantity}× " if quantity != "" else ""
        item_lines = [f"{qty_bit}{item_name}"]
    bullets = _bullet_block(item_lines, empty="- (see order)")

    help_lines = _help_lines(ctx.get("coordinators") or [])
    help_block = (
        "\n".join(help_lines) if help_lines else "- (nobody listed yet)"
    )

    title = "You're on the order!"
    phrase = _body_item_phrase(item_lines)
    body = (
        f"{phrase}. When you're finished, open the delivery link."
        if phrase
        else "When you're finished, open the delivery link."
    )
    discord = (
        f"You're on the order!\n\n"
        f"{bullets}\n\n"
        f"**Who can help**\n"
        f"{help_block}\n\n"
        f"When you're finished, click [here]({delivery_url}) for delivery."
    )
    eve_body = (
        f"You're on the order!\n\n"
        f"{bullets}\n\n"
        f"Who can help\n{help_block}\n\n"
        f"When you're finished, open this for delivery:\n{delivery_url}\n\n"
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
    item_name = ctx.get("item_name") or "your build"
    assignment_id = ctx["assignment_id"]
    item_id = ctx["item_id"]
    delivery_url = _contract_url(order_id, item_id, assignment_id)

    title = "We've detected an order blueprint cooking!"
    body = f"When it's done, open delivery steps for {item_name}."
    discord = (
        f"We've detected an order blueprint cooking!\n\n"
        f"When it's done, [click here]({delivery_url}) for delivery steps."
    )
    eve_body = (
        f"We've detected an order blueprint cooking!\n\n"
        f"When it's done, open this for delivery steps:\n{delivery_url}\n\n"
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
