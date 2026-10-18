"""Discord forum-thread mirror for hangar buyback purchase orders."""

from __future__ import annotations

import logging

from django.conf import settings

from buyback.helpers.purchase_discord_buttons import order_action_components
from buyback.models import BuybackPurchaseOrder
from discord.client import DiscordClient
from discord.forum_threads import ForumThreadMirror

logger = logging.getLogger(__name__)
discord = DiscordClient()

STARTER_CONTENT_LIMIT = 1800


def _close_task():
    # pylint: disable=import-outside-toplevel
    from buyback.discord_tasks import close_buyback_purchase_thread_task

    return close_buyback_purchase_thread_task


MIRROR = ForumThreadMirror(
    label="hangar buyback",
    channel_flag="receive_buyback",
    preferred_tags=frozenset(
        {"open", "purchase-order", "buyback", "order", "new"}
    ),
    client=lambda: discord,
    close_task=_close_task,
)


def order_site_url(order: BuybackPurchaseOrder) -> str:
    base = getattr(settings, "WEB_LINK_URL", "https://my.minmatar.org").rstrip(
        "/"
    )
    return f"{base}/market/buyback/orders/?order={int(order.pk)}"


def discord_thread_url(thread_id: int | None) -> str | None:
    if not thread_id:
        return None
    guild_id = getattr(settings, "DISCORD_GUILD_ID", None)
    if not guild_id:
        return None
    return f"https://discord.com/channels/{guild_id}/{int(thread_id)}"


def _user_mention(user) -> str:
    if user is None:
        return ""
    try:
        return f"<@{user.discord_user.id}>"
    except Exception:
        return user.username


def _display_name(order: BuybackPurchaseOrder) -> str:
    return order.character_name or (
        order.created_by.username if order.created_by_id else "?"
    )


def format_isk_compact(isk: int) -> str:
    """Human ISK amount for titles (e.g. 3.5M, 850K)."""
    qty = int(isk)
    if qty >= 1_000_000_000:
        value = qty / 1_000_000_000
        text = f"{value:.1f}".rstrip("0").rstrip(".")
        return f"{text}B"
    if qty >= 1_000_000:
        value = qty / 1_000_000
        text = f"{value:.1f}".rstrip("0").rstrip(".")
        return f"{text}M"
    if qty >= 1_000:
        value = qty / 1_000
        text = f"{value:.1f}".rstrip("0").rstrip(".")
        return f"{text}K"
    return f"{qty:,}"


def buyback_channel_id() -> int | None:
    return MIRROR.channel_id()


def order_thread_title(order: BuybackPurchaseOrder) -> str:
    who = _display_name(order)
    isk = format_isk_compact(order.contract_total)
    return f"Sale #{order.pk} · {who} · {isk} ISK"


def _starter_with_items(
    header: list[str],
    items: list[str],
    omitted: int,
    url: str,
) -> str:
    extra = [f"- …and {omitted} more line(s)"] if omitted else []
    return "\n".join(header + items + extra + [url])


def order_starter_message(order: BuybackPurchaseOrder) -> str:
    mention = _user_mention(order.created_by)
    header = [
        mention,
        "",
        f"**Purchase order #{order.pk}**",
        f"Pilot: {_display_name(order)}",
        f"Total: **{int(order.contract_total):,} ISK**",
        f"Status: {order.get_status_display()}",
        "",
    ]
    item_lines = [
        f"- {line.quantity:,}× {line.name}" for line in order.lines.all()
    ]
    url = order_site_url(order)
    full = _starter_with_items(header, item_lines, 0, url)
    if len(full) <= STARTER_CONTENT_LIMIT:
        return full

    kept: list[str] = []
    for index, item in enumerate(item_lines):
        omitted = len(item_lines) - (index + 1)
        candidate = _starter_with_items(header, kept + [item], omitted, url)
        if len(candidate) > STARTER_CONTENT_LIMIT:
            omitted_all = len(item_lines) - len(kept)
            fallback = _starter_with_items(header, kept, omitted_all, url)
            if len(fallback) <= STARTER_CONTENT_LIMIT:
                return fallback
            return full[: STARTER_CONTENT_LIMIT - 1] + "…"
        kept.append(item)
    return _starter_with_items(header, kept, 0, url)


def create_order_thread(order: BuybackPurchaseOrder) -> int | None:
    return MIRROR.create_thread(
        order_thread_title(order),
        order_starter_message(order),
        components=order_action_components(order.pk),
    )


def close_thread_id(thread_id: int | None) -> bool:
    """Archive/lock a purchase-order thread by Discord channel id."""
    return MIRROR.close(thread_id)


def close_order_thread(order: BuybackPurchaseOrder) -> None:
    """Archive/lock the order thread without posting (avoids Discord reopen race)."""
    MIRROR.close(order.discord_thread_id)


def post_order_status_update(
    order: BuybackPurchaseOrder,
    *,
    message: str,
) -> None:
    MIRROR.post(order.discord_thread_id, message)


def notify_purchase_created(order: BuybackPurchaseOrder) -> None:
    thread_id = create_order_thread(order)
    if thread_id:
        BuybackPurchaseOrder.objects.filter(pk=order.pk).update(
            discord_thread_id=thread_id
        )
        order.discord_thread_id = thread_id


def _completed_message(order: BuybackPurchaseOrder) -> str:
    if order.completed_by_id:
        actor = _user_mention(order.completed_by) or (
            order.completed_by.username if order.completed_by else ""
        )
        who = f" by **{actor}**" if actor else ""
    else:
        who = " (contract matched)"
    mention = _user_mention(order.created_by)
    lines: list[str] = []
    if mention:
        lines.extend([mention, ""])
    lines.extend(
        [
            f":white_check_mark: Sale completed{who}",
            f"**{int(order.contract_total):,} ISK**",
            order_site_url(order),
        ]
    )
    return "\n".join(lines)


def _cancelled_message(order: BuybackPurchaseOrder) -> str:
    mention = _user_mention(order.created_by)
    lines: list[str] = []
    if mention:
        lines.extend([mention, ""])
    lines.extend(
        [
            ":no_entry_sign: Sale cancelled",
            order_site_url(order),
        ]
    )
    return "\n".join(lines)


def notify_purchase_status_changed(order: BuybackPurchaseOrder) -> None:
    if not order.discord_thread_id:
        return
    if order.status == BuybackPurchaseOrder.Status.COMPLETED:
        MIRROR.post_then_close(
            order.discord_thread_id, _completed_message(order)
        )
    elif order.status == BuybackPurchaseOrder.Status.CANCELLED:
        MIRROR.post_then_close(
            order.discord_thread_id, _cancelled_message(order)
        )
