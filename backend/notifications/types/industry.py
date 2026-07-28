"""Industry order notification type definitions and renderers."""

from __future__ import annotations

from django.conf import settings

from notifications.models import NotificationChannel
from notifications.registry import NotificationType, register


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


def render_order_created(ctx: dict) -> dict:
    order_id = ctx["order_id"]
    short = ctx.get("public_short_code") or str(order_id)
    needed_by = ctx.get("needed_by") or ""
    items = ctx.get("items_summary") or ""
    location = ctx.get("location_name") or ""
    url = _order_url(order_id)
    title = f"New industry order {short}"
    body_parts = [f"Needed by {needed_by}" if needed_by else "New order"]
    if location:
        body_parts.append(location)
    if items:
        body_parts.append(items)
    body = " · ".join(body_parts)
    return {
        "title": title,
        "body": body,
        "url": url,
        "discord_message": (
            f"**New industry order `{short}`**\n{body}\n{url}"
        ),
        "subject": title,
        "eve_mail_body": (
            f"A new industry order ({short}) is available.\n\n"
            f"{body}\n\nView: {url}\n\n"
            f"Best,\nBearThatCares"
        ),
    }


def render_order_assignment(ctx: dict) -> dict:
    order_id = ctx["order_id"]
    short = ctx.get("public_short_code") or str(order_id)
    item_name = ctx.get("item_name") or "item"
    quantity = ctx.get("quantity") or ""
    assignment_id = ctx["assignment_id"]
    item_id = ctx["item_id"]
    delivery_url = _contract_url(order_id, item_id, assignment_id)
    order_url = _order_url(order_id)
    coordinators = ctx.get("coordinators") or []
    coord_lines = []
    for c in coordinators:
        role = c.get("role") or "coordinator"
        name = c.get("character_name") or "?"
        types = ", ".join(c.get("eve_type_names") or []) or "general"
        coord_lines.append(f"- {name} ({role}): {types}")
    coord_block = (
        "\n".join(coord_lines) if coord_lines else "- None listed yet"
    )
    title = f"Assigned to order {short}"
    body = (
        f"You claimed {quantity}× {item_name} on order {short}. "
        f"When finished, use the delivery steps."
    )
    discord = (
        f"**Assigned to order `{short}`**\n"
        f"{quantity}× {item_name}\n\n"
        f"**Coordinators**\n{coord_block}\n\n"
        f"Delivery steps: {delivery_url}\n"
        f"Order: {order_url}"
    )
    eve_body = (
        f"You assigned yourself to order {short}: {quantity}× {item_name}.\n\n"
        f"Coordinators:\n{coord_block}\n\n"
        f"When done, follow delivery steps:\n{delivery_url}\n\n"
        f"Best,\nBearThatCares"
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
    item_name = ctx.get("item_name") or "item"
    assignment_id = ctx["assignment_id"]
    item_id = ctx["item_id"]
    job_id = ctx.get("job_id")
    delivery_url = _contract_url(order_id, item_id, assignment_id)
    title = f"Industry job started for order {short}"
    body = (
        f"We saw a manufacturing job for {item_name} on order {short}. "
        f"Remember to deliver when complete."
    )
    discord = (
        f"**Job detected for order `{short}`**\n"
        f"{item_name}"
        + (f" (job {job_id})" if job_id else "")
        + f"\n\nDelivery steps when finished: {delivery_url}"
    )
    eve_body = (
        f"We detected an industry job for {item_name} on order {short}.\n\n"
        f"When the job completes, deliver via:\n{delivery_url}\n\n"
        f"Best,\nBearThatCares"
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
        label="New orders",
        description=(
            "When a new industry order is posted. Audience includes recent "
            "order participants and anyone subscribed to this topic."
        ),
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
        label="Assignment confirmation",
        description=(
            "When you assign yourself to an order line: coordinators and "
            "delivery steps."
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
        label="Job started reminder",
        description=(
            "When we detect a manufacturing job for a blueprint on an "
            "assignment you hold — reminds you of the delivery link."
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
