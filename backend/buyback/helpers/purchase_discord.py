"""Discord forum-thread mirror for hangar buyback purchase orders."""

from __future__ import annotations

import logging
import time

from django.conf import settings

from buyback.helpers.purchase_discord_buttons import order_action_components
from buyback.models import BuybackPurchaseOrder
from discord.client import DiscordClient
from discord.models import DiscordChannel

logger = logging.getLogger(__name__)
discord = DiscordClient()

# Match LP buyback / help tickets: settle message traffic before archive so
# Discord does not reopen the thread when a post lands after close.
THREAD_ARCHIVE_DELAY_SECONDS = 5
STARTER_CONTENT_LIMIT = 1800


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
    channel_id = (
        DiscordChannel.objects.filter(
            receive_buyback=True,
            guild__is_active=True,
        )
        .values_list("channel_id", flat=True)
        .first()
    )
    return int(channel_id) if channel_id else None


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


def _default_forum_tag_ids(channel_id: int) -> list[str]:
    try:
        channel = discord.get_channel(channel_id).json()
    except Exception as exc:
        logger.warning(
            "Could not fetch buyback forum channel %s for tags: %s",
            channel_id,
            exc,
        )
        return []

    tags = channel.get("available_tags") or []
    if not tags:
        return []

    preferred_names = {
        "open",
        "purchase-order",
        "buyback",
        "order",
        "new",
    }
    for tag in tags:
        name = str(tag.get("name") or "").strip().lower()
        if name in preferred_names:
            return [str(tag["id"])]
    return [str(tags[0]["id"])]


def create_order_thread(order: BuybackPurchaseOrder) -> int | None:
    channel_id = buyback_channel_id()
    if not channel_id:
        logger.warning("No DiscordChannel with receive_buyback; skip thread")
        return None
    try:
        response = discord.create_forum_thread(
            channel_id=channel_id,
            title=order_thread_title(order)[:100],
            message=order_starter_message(order),
            applied_tags=_default_forum_tag_ids(channel_id),
            components=order_action_components(order.pk),
        )
        return int(response.json()["id"])
    except Exception as exc:
        logger.error(
            "Failed creating hangar buyback Discord thread (channel=%s): %s",
            channel_id,
            exc,
        )
        return None


def close_order_thread(order: BuybackPurchaseOrder) -> None:
    """Archive/lock the order thread without posting (avoids Discord reopen race)."""
    if not order.discord_thread_id:
        return
    try:
        discord.close_thread(channel_id=order.discord_thread_id)
    except Exception as exc:
        logger.error("Failed closing hangar buyback Discord thread: %s", exc)


def post_order_status_update(
    order: BuybackPurchaseOrder,
    *,
    message: str,
) -> None:
    if not order.discord_thread_id:
        return
    try:
        discord.create_message(
            channel_id=order.discord_thread_id, payload={"content": message}
        )
    except Exception as exc:
        logger.error("Failed posting hangar buyback Discord update: %s", exc)


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


def _post_then_archive(order: BuybackPurchaseOrder, message: str) -> None:
    post_order_status_update(order, message=message)
    time.sleep(THREAD_ARCHIVE_DELAY_SECONDS)
    close_order_thread(order)


def notify_purchase_status_changed(order: BuybackPurchaseOrder) -> None:
    if not order.discord_thread_id:
        return
    if order.status == BuybackPurchaseOrder.Status.COMPLETED:
        _post_then_archive(order, _completed_message(order))
    elif order.status == BuybackPurchaseOrder.Status.CANCELLED:
        _post_then_archive(order, _cancelled_message(order))
