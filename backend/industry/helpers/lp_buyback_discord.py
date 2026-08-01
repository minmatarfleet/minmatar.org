"""Discord forum-thread mirror for LP buyback market orders."""

from __future__ import annotations

import logging

from django.conf import settings

from discord.client import DiscordClient
from discord.models import DiscordChannel
from eveonline.helpers.characters import user_primary_character
from industry.helpers.lp_buyback_discord_buttons import (
    isk_sent_components,
    lp_sent_components,
)
from industry.helpers.lp_market_orders import (
    currency_short_name,
    format_lp_quantity,
    remaining_quantity,
)
from industry.models import IndustryLoyaltyPointMarketOrder

logger = logging.getLogger(__name__)
discord = DiscordClient()


def order_site_url(order: IndustryLoyaltyPointMarketOrder) -> str:
    base = getattr(settings, "WEB_LINK_URL", "https://my.minmatar.org").rstrip(
        "/"
    )
    return f"{base}/industry/loyalty/?order={order.pk}"


def _user_mention(user) -> str:
    if user is None:
        return ""
    try:
        return f"<@{user.discord_user.id}>"
    except Exception:
        return user.username


def _display_name(user) -> str:
    if user is None:
        return "?"
    primary = user_primary_character(user)
    if primary:
        return primary.character_name
    return user.username


def lp_sender(order: IndustryLoyaltyPointMarketOrder):
    if order.side == order.Side.SELL:
        return order.created_by
    return order.claimed_by


def isk_payer(order: IndustryLoyaltyPointMarketOrder):
    if order.side == order.Side.SELL:
        return order.claimed_by
    return order.created_by


def lp_buyback_channel_id() -> int | None:
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
        "",
        f"**{side_label}** {order.quantity:,} "
        f"{order.loyalty_point.name} @ {order.isk_per_lp} ISK/LP",
        f"Pilot: {_display_name(order.created_by)}",
        f"Status: {order.get_status_display()}",
    ]
    if order.notes:
        parts.append(f"Notes: {order.notes}")
    parts.append(order_site_url(order))
    return "\n".join(parts)


def _default_forum_tag_ids(channel_id: int) -> list[str]:
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
    components: list[dict] | None = None,
    close: bool = False,
) -> None:
    if not order.discord_thread_id:
        return
    payload = {"content": message}
    if components:
        payload["components"] = components
    try:
        discord.create_message(
            channel_id=order.discord_thread_id, payload=payload
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


def _destination_label(
    order: IndustryLoyaltyPointMarketOrder,
    *,
    claim=None,
) -> str:
    if claim is not None:
        dest_parts = []
        if claim.destination_character_name:
            dest_parts.append(claim.destination_character_name)
        if claim.destination_corporation_name:
            dest_parts.append(claim.destination_corporation_name)
        if dest_parts:
            return " / ".join(dest_parts)
    return (order.destination_character_name or "").strip() or "(unset)"


def _send_lp_line(
    order: IndustryLoyaltyPointMarketOrder,
    sender,
    *,
    claim=None,
) -> str:
    dest = _destination_label(order, claim=claim)
    if dest == "(unset)":
        return ""
    mention = _user_mention(sender)
    prefix = f"{mention} " if mention else ""
    return f"\n{prefix}Send LP to: **{dest}**"


def notify_order_claimed(
    order: IndustryLoyaltyPointMarketOrder,
    *,
    claim=None,
) -> None:
    claimer_user = claim.claimed_by if claim is not None else order.claimed_by
    claimer = _display_name(claimer_user)
    sender = lp_sender(order)
    if claim is not None:
        remaining = remaining_quantity(order)
        label = "Partial claim" if remaining > 0 else "Claim"
        msg = (
            f":handshake: {label} by **{claimer}**: "
            f"**{int(claim.amount):,}** LP"
        )
        msg += _send_lp_line(order, sender, claim=claim)
        if remaining > 0:
            msg += f"\nRemaining: **{remaining:,}** LP (still open)"
        else:
            msg += f"\nStatus: {order.get_status_display()}"
    else:
        msg = f":handshake: Claimed by **{claimer}**\nStatus: Claimed"
        msg += _send_lp_line(order, sender)
    msg += f"\n{order_site_url(order)}"
    post_order_status_update(order, message=msg)


def _awaiting_lp_message(order: IndustryLoyaltyPointMarketOrder) -> str:
    return "\n".join(
        [
            _user_mention(lp_sender(order)),
            "",
            ":package: Awaiting LP transfer",
            f"Claimed by **{_display_name(order.claimed_by)}**",
            f"Send LP to: **{_destination_label(order)}**",
            order_site_url(order),
        ]
    )


def _awaiting_isk_message(order: IndustryLoyaltyPointMarketOrder) -> str:
    return "\n".join(
        [
            _user_mention(isk_payer(order)),
            "",
            ":moneybag: LP received — awaiting ISK payment",
            f"Pay ISK to: **{_display_name(lp_sender(order))}**",
            order_site_url(order),
        ]
    )


def notify_order_status_changed(
    order: IndustryLoyaltyPointMarketOrder,
) -> None:
    status = order.status
    if status == order.Status.AWAITING_LP:
        post_order_status_update(
            order,
            message=_awaiting_lp_message(order),
            components=lp_sent_components(order.pk),
        )
    elif status == order.Status.AWAITING_ISK:
        post_order_status_update(
            order,
            message=_awaiting_isk_message(order),
            components=isk_sent_components(order.pk),
        )
    elif status == order.Status.COMPLETED:
        post_order_status_update(
            order,
            message=f":white_check_mark: Completed\n{order_site_url(order)}",
            close=True,
        )
    elif status == order.Status.CANCELLED:
        post_order_status_update(
            order,
            message=f":x: Cancelled\n{order_site_url(order)}",
            close=True,
        )
