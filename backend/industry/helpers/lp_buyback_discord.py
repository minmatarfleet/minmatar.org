"""Discord forum-thread mirror for LP buyback market orders."""

from __future__ import annotations

import logging

from django.conf import settings

from discord.client import DiscordClient
from discord.models import DiscordChannel
from eveonline.helpers.characters import user_primary_character
from industry.helpers.lp_market_orders import (
    currency_short_name,
    format_lp_quantity,
    remaining_quantity,
)
from industry.models import IndustryLoyaltyPointMarketOrder
from tribes.models import TribeGroup

logger = logging.getLogger(__name__)
discord = DiscordClient()

LOYALTY_POINTS_TRIBE_CODE = "supply.loyalty-points"


def order_site_url(order: IndustryLoyaltyPointMarketOrder) -> str:
    base = getattr(settings, "WEB_LINK_URL", "https://my.minmatar.org").rstrip(
        "/"
    )
    return f"{base}/industry/loyalty/?order={order.pk}"


def _conversion_role_mention() -> str:
    tg = (
        TribeGroup.objects.filter(
            code=LOYALTY_POINTS_TRIBE_CODE, is_active=True
        )
        .select_related("group")
        .first()
    )
    if not tg or not tg.group_id:
        return ""
    try:
        discord_group = tg.group.discord_group
    except Exception:
        return ""
    if not discord_group or not discord_group.role_id:
        return ""
    return f"<@&{discord_group.role_id}>"


def _user_mention(user) -> str:
    try:
        return f"<@{user.discord_user.id}>"
    except Exception:
        return user.username


def _display_name(user) -> str:
    primary = user_primary_character(user)
    if primary:
        return primary.character_name
    return user.username


def lp_buyback_channel_id() -> int | None:
    """Forum channel designated for LP buyback order threads, if any."""
    channel_id = (
        DiscordChannel.objects.filter(
            receive_lp_buyback=True,
            guild__is_active=True,
        )
        .values_list("channel_id", flat=True)
        .first()
    )
    return int(channel_id) if channel_id else None


def order_thread_title(order: IndustryLoyaltyPointMarketOrder) -> str:
    side = "WTS" if order.side == order.Side.SELL else "WTB"
    qty = format_lp_quantity(order.quantity)
    short = currency_short_name(order.loyalty_point.name)
    return f"{side} {qty} {short} @{order.isk_per_lp}"


def order_starter_message(order: IndustryLoyaltyPointMarketOrder) -> str:
    side_label = "Sell" if order.side == order.Side.SELL else "Buy"
    parts = [
        _user_mention(order.created_by),
        _conversion_role_mention(),
        "",
        f"**{side_label}** {order.quantity:,} "
        f"{order.loyalty_point.name} @ {order.isk_per_lp} ISK/LP",
        f"Pilot: {_display_name(order.created_by)}",
        f"Status: {order.get_status_display()}",
    ]
    if order.notes:
        parts.append(f"Notes: {order.notes}")
    parts.append(order_site_url(order))
    return "\n".join(p for p in parts if p is not None)


def _default_forum_tag_ids(channel_id: int) -> list[str]:
    """Pick applied_tags for the LP buyback forum (needed when REQUIRE_TAG)."""
    try:
        channel = discord.get_channel(channel_id).json()
    except Exception as exc:
        logger.warning(
            "Could not fetch LP buyback forum channel %s for tags: %s",
            channel_id,
            exc,
        )
        return []

    tags = channel.get("available_tags") or []
    if not tags:
        return []

    preferred_names = {"open", "buyback", "order", "new", "wts", "wtb"}
    for tag in tags:
        name = str(tag.get("name") or "").strip().lower()
        if name in preferred_names:
            return [str(tag["id"])]
    return [str(tags[0]["id"])]


def create_order_thread(order: IndustryLoyaltyPointMarketOrder) -> int | None:
    """Create #lp-buyback forum thread; return thread id or None on skip/fail."""
    channel_id = lp_buyback_channel_id()
    if not channel_id:
        logger.warning(
            "No DiscordChannel with receive_lp_buyback; skip thread"
        )
        return None
    try:
        response = discord.create_forum_thread(
            channel_id=channel_id,
            title=order_thread_title(order)[:100],
            message=order_starter_message(order),
            applied_tags=_default_forum_tag_ids(channel_id),
        )
        return int(response.json()["id"])
    except Exception as exc:
        logger.error(
            "Failed creating LP buyback Discord thread (channel=%s): %s",
            channel_id,
            exc,
        )
        return None


def post_order_status_update(
    order: IndustryLoyaltyPointMarketOrder,
    *,
    message: str,
    close: bool = False,
) -> None:
    if not order.discord_thread_id:
        return
    try:
        discord.create_message(
            channel_id=order.discord_thread_id, message=message
        )
    except Exception as exc:
        logger.error("Failed posting LP buyback Discord update: %s", exc)
        return
    if close:
        try:
            discord.close_thread(channel_id=order.discord_thread_id)
        except Exception as exc:
            logger.error("Failed closing LP buyback Discord thread: %s", exc)


def notify_order_created(order: IndustryLoyaltyPointMarketOrder) -> None:
    thread_id = create_order_thread(order)
    if thread_id:
        IndustryLoyaltyPointMarketOrder.objects.filter(pk=order.pk).update(
            discord_thread_id=thread_id
        )
        order.discord_thread_id = thread_id


def notify_order_claimed(
    order: IndustryLoyaltyPointMarketOrder,
    *,
    claim=None,
) -> None:
    claimer_user = claim.claimed_by if claim is not None else order.claimed_by
    claimer = _display_name(claimer_user) if claimer_user else "?"
    if claim is not None:
        remaining = remaining_quantity(order)
        label = "Partial claim" if remaining > 0 else "Claim"
        msg = (
            f":handshake: {label} by **{claimer}**: "
            f"**{int(claim.amount):,}** LP"
        )
        dest_parts = []
        if claim.destination_character_name:
            dest_parts.append(claim.destination_character_name)
        if claim.destination_corporation_name:
            dest_parts.append(claim.destination_corporation_name)
        if dest_parts:
            msg += f"\nSend LP to: **{' / '.join(dest_parts)}**"
        if remaining > 0:
            msg += f"\nRemaining: **{remaining:,}** LP (still open)"
        else:
            msg += f"\nStatus: {order.get_status_display()}"
    else:
        msg = f":handshake: Claimed by **{claimer}**\nStatus: Claimed"
        if order.destination_character_name:
            msg += f"\nSend LP to: **{order.destination_character_name}**"
    msg += f"\n{order_site_url(order)}"
    post_order_status_update(order, message=msg)


def notify_order_status_changed(
    order: IndustryLoyaltyPointMarketOrder,
) -> None:
    status = order.status
    if status == order.Status.AWAITING_LP:
        dest = order.destination_character_name or "(unset)"
        msg = (
            f":package: Awaiting LP transfer\n"
            f"Send LP to: **{dest}**\n{order_site_url(order)}"
        )
        post_order_status_update(order, message=msg)
    elif status == order.Status.AWAITING_ISK:
        msg = (
            f":moneybag: LP received — awaiting ISK payment\n"
            f"{order_site_url(order)}"
        )
        post_order_status_update(order, message=msg)
    elif status == order.Status.COMPLETED:
        msg = f":white_check_mark: Completed\n{order_site_url(order)}"
        post_order_status_update(order, message=msg, close=True)
    elif status == order.Status.CANCELLED:
        msg = f":x: Cancelled\n{order_site_url(order)}"
        post_order_status_update(order, message=msg, close=True)
