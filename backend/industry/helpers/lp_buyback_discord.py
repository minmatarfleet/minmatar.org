"""Discord forum-thread mirror for LP buyback market orders."""

from __future__ import annotations

import logging
import time

from django.conf import settings

from discord.client import DiscordClient
from discord.models import DiscordChannel
from eveonline.helpers.characters import user_primary_character
from industry.helpers.lp_buyback_discord_buttons import (
    isk_sent_components,
    lp_sent_components,
)
from industry.helpers.lp_market_orders import (
    PRE_LP_STATUSES,
    TERMINAL_STATUSES,
    claimed_quantity,
    currency_short_name,
    format_lp_quantity,
    remaining_quantity,
)
from industry.models import IndustryLoyaltyPointMarketOrder

logger = logging.getLogger(__name__)
discord = DiscordClient()

# Match help tickets / bot ISK-sent: settle message traffic before archive so
# Discord does not reopen the thread when a post lands after close.
THREAD_ARCHIVE_DELAY_SECONDS = 5

# Deleted orders 122/123 and cancelled order 130 (thread created after cancel).
ORPHAN_LP_BUYBACK_THREAD_IDS = (
    1541754525805842462,
    1541754700171452416,
    1542512504742346832,
)

# Keeps the Conversion Team digest under Discord's 2,000-character cap.
STALE_DIGEST_MAX_LINES = 15


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


def _flagged_channel_row(flag: str) -> tuple[int, int] | None:
    """(channel_id, guild_id) of the active channel with this receive_* flag."""
    row = (
        DiscordChannel.objects.filter(**{flag: True}, guild__is_active=True)
        .values_list("channel_id", "guild__guild_id")
        .first()
    )
    if not row or not row[0]:
        return None
    return int(row[0]), int(row[1])


def _lp_buyback_channel_row() -> tuple[int, int] | None:
    return _flagged_channel_row("receive_lp_buyback")


def lp_conversion_alert_channel_id() -> int | None:
    row = _flagged_channel_row("receive_lp_conversion_alerts")
    return row[0] if row else None


def lp_buyback_channel_id() -> int | None:
    row = _lp_buyback_channel_row()
    return row[0] if row else None


def active_lp_buyback_thread_ids() -> set[int] | None:
    """Unarchived thread ids in the buyback forum (None if unknown)."""
    row = _lp_buyback_channel_row()
    if not row:
        return None
    channel_id, guild_id = row
    try:
        threads = (
            DiscordClient(guild_id=guild_id)
            .get_active_threads()
            .json()
            .get("threads", [])
        )
    except Exception as exc:
        logger.warning("Could not list active LP buyback threads: %s", exc)
        return None
    return {
        int(thread["id"])
        for thread in threads
        if str(thread.get("parent_id")) == str(channel_id)
    }


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
    if (
        order.side == order.Side.BUY
        and (order.destination_character_name or "").strip()
    ):
        parts.append(
            f"Send LP to: **{order.destination_character_name.strip()}**"
        )
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


def close_lp_buyback_thread_id(thread_id: int | None) -> bool:
    """Archive/lock a buyback forum thread by Discord channel id."""
    if not thread_id:
        return False
    try:
        discord.close_thread(channel_id=int(thread_id))
        return True
    except Exception as exc:
        logger.error(
            "Failed closing LP buyback Discord thread %s: %s", thread_id, exc
        )
        return False


def close_order_thread(order: IndustryLoyaltyPointMarketOrder) -> None:
    """Archive/lock the order thread without posting (avoids Discord reopen race)."""
    close_lp_buyback_thread_id(order.discord_thread_id)


def post_order_status_update(
    order: IndustryLoyaltyPointMarketOrder,
    *,
    message: str,
    components: list[dict] | None = None,
) -> bool:
    """Post in the order thread; False when there is no thread or it failed."""
    if not order.discord_thread_id:
        return False
    payload = {"content": message}
    if components:
        payload["components"] = components
    try:
        discord.create_message(
            channel_id=order.discord_thread_id, payload=payload
        )
    except Exception as exc:
        logger.error("Failed posting LP buyback Discord update: %s", exc)
        return False
    return True


def notify_order_created(order: IndustryLoyaltyPointMarketOrder) -> None:
    try:
        current = IndustryLoyaltyPointMarketOrder.objects.select_related(
            "loyalty_point", "created_by"
        ).get(pk=order.pk)
    except IndustryLoyaltyPointMarketOrder.DoesNotExist:
        return
    if current.status in TERMINAL_STATUSES:
        close_order_thread(current)
        return
    # The create task and the hourly sweep's retry can both get here; only
    # the first thread is kept.
    if current.discord_thread_id:
        return

    thread_id = create_order_thread(current)
    if not thread_id:
        return

    attached = (
        IndustryLoyaltyPointMarketOrder.objects.filter(
            pk=current.pk, discord_thread_id__isnull=True
        )
        .exclude(status__in=TERMINAL_STATUSES)
        .update(discord_thread_id=thread_id)
    )
    if not attached:
        close_lp_buyback_thread_id(thread_id)
        return
    current.discord_thread_id = thread_id


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


def _lp_quantity_for_isk(
    order: IndustryLoyaltyPointMarketOrder,
    *,
    claim=None,
) -> int:
    """LP quantity used to compute ISK due for payment prompts."""
    if claim is not None:
        return int(claim.amount)
    claimed = claimed_quantity(order)
    if claimed > 0:
        return claimed
    return int(order.quantity)


def _isk_due(
    order: IndustryLoyaltyPointMarketOrder,
    *,
    claim=None,
) -> int:
    return _lp_quantity_for_isk(order, claim=claim) * int(order.isk_per_lp)


def _pay_isk_line(
    order: IndustryLoyaltyPointMarketOrder,
    *,
    claim=None,
) -> str:
    """ISK payout line (amount + destination)."""
    dest = _destination_label(order, claim=claim)
    if dest == "(unset)":
        return ""
    mention = _user_mention(isk_payer(order))
    prefix = f"{mention} " if mention else ""
    isk = _isk_due(order, claim=claim)
    return f"\n{prefix}Pay **{isk:,} ISK** to **{dest}**"


def _isk_due_line(
    order: IndustryLoyaltyPointMarketOrder,
    *,
    claim=None,
) -> str:
    """ISK total for sell claims where destination is set later."""
    lp = _lp_quantity_for_isk(order, claim=claim)
    isk = _isk_due(order, claim=claim)
    return f"\nISK due: **{isk:,} ISK** ({lp:,} LP @ {order.isk_per_lp})"


def _isk_payout_label(order: IndustryLoyaltyPointMarketOrder) -> str:
    """Where ISK should be paid for awaiting-ISK messages."""
    if order.side == order.Side.BUY:
        claim = (
            order.claims.order_by("-created_at", "-id").first()
            if hasattr(order, "claims")
            else None
        )
        if claim is not None:
            dest = _destination_label(order, claim=claim)
            if dest != "(unset)":
                return dest
    return _display_name(lp_sender(order))


def notify_order_claims_released(
    order: IndustryLoyaltyPointMarketOrder,
    *,
    released_by,
    released_amount: int,
) -> None:
    """Announce that claims were released and the order is open again."""
    actor = _display_name(released_by)
    remaining = remaining_quantity(order)
    msg = (
        f":arrows_counterclockwise: Claim released by **{actor}** "
        f"({int(released_amount):,} LP).\n"
        f"Status: Open — **{remaining:,}** LP available\n"
        f"{order_site_url(order)}"
    )
    post_order_status_update(order, message=msg)


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
        if order.side == order.Side.BUY:
            msg += _pay_isk_line(order, claim=claim)
        else:
            msg += _send_lp_line(order, sender, claim=claim)
            msg += _isk_due_line(order, claim=claim)
        if remaining > 0:
            msg += f"\nRemaining: **{remaining:,}** LP (still open)"
        else:
            msg += f"\nStatus: {order.get_status_display()}"
    else:
        msg = f":handshake: Claimed by **{claimer}**\nStatus: Claimed"
        if order.side == order.Side.BUY:
            msg += _pay_isk_line(order)
        else:
            msg += _send_lp_line(order, sender)
            msg += _isk_due_line(order)
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
            "",
            "Take a screenshot of the LP transfer and paste it in this thread.",
            order_site_url(order),
        ]
    )


def _awaiting_isk_message(order: IndustryLoyaltyPointMarketOrder) -> str:
    lp = _lp_quantity_for_isk(order)
    isk = _isk_due(order)
    return "\n".join(
        [
            _user_mention(isk_payer(order)),
            "",
            ":moneybag: LP received — awaiting ISK payment",
            f"Pay **{isk:,} ISK** to **{_isk_payout_label(order)}**",
            f"{lp:,} LP @ {order.isk_per_lp} ISK/LP",
            order_site_url(order),
        ]
    )


def _completed_message(order: IndustryLoyaltyPointMarketOrder) -> str:
    """Public completion notice; pings the LP sender (ISK recipient)."""
    lp = _lp_quantity_for_isk(order)
    isk = _isk_due(order)
    mention = _user_mention(lp_sender(order))
    lines: list[str] = []
    if mention:
        lines.extend([mention, ""])
    lines.extend(
        [
            ":white_check_mark: ISK sent — order completed",
            f"**{isk:,} ISK** for {lp:,} LP @ {order.isk_per_lp} ISK/LP",
            order_site_url(order),
        ]
    )
    return "\n".join(lines)


def _post_completed_then_archive(
    order: IndustryLoyaltyPointMarketOrder,
) -> None:
    """Post completion, wait, then archive (avoids Discord reopen race)."""
    post_order_status_update(order, message=_completed_message(order))
    time.sleep(THREAD_ARCHIVE_DELAY_SECONDS)
    close_order_thread(order)


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
        # Post first, wait, then archive — never post after close (Discord
        # unarchives). Caller must invoke after DB commit (see transition_order).
        _post_completed_then_archive(order)


def _order_participants(order: IndustryLoyaltyPointMarketOrder) -> list:
    """Creator plus every claimer, deduplicated, creator first."""
    users = [order.created_by, order.claimed_by]
    users.extend(claim.claimed_by for claim in order.claims.all())
    seen: set[int] = set()
    unique = []
    for user in users:
        if user is None or user.pk in seen:
            continue
        seen.add(user.pk)
        unique.append(user)
    return unique


def _cancelled_message(
    order: IndustryLoyaltyPointMarketOrder,
    *,
    cancelled_by=None,
    reason: str = "",
) -> str:
    mentions = " ".join(
        mention
        for mention in (_user_mention(u) for u in _order_participants(order))
        if mention
    )
    lines: list[str] = []
    if mentions:
        lines.extend([mentions, ""])
    if cancelled_by is not None:
        lines.append(
            f":x: Order cancelled by **{_display_name(cancelled_by)}**"
        )
    else:
        lines.append(":x: Order cancelled")
    if reason:
        lines.append(reason)
    lines.append(order_site_url(order))
    return "\n".join(lines)


def notify_order_cancelled(
    order: IndustryLoyaltyPointMarketOrder,
    *,
    cancelled_by=None,
    reason: str = "",
) -> None:
    """Post the cancellation, wait, then archive (avoids reopen race)."""
    if not order.discord_thread_id:
        return
    post_order_status_update(
        order,
        message=_cancelled_message(
            order, cancelled_by=cancelled_by, reason=reason
        ),
    )
    time.sleep(THREAD_ARCHIVE_DELAY_SECONDS)
    close_order_thread(order)


def waiting_on(order: IndustryLoyaltyPointMarketOrder):
    """The user whose action the order is waiting on, if any."""
    if order.status == order.Status.AWAITING_LP:
        return lp_sender(order)
    if order.status == order.Status.AWAITING_ISK:
        return isk_payer(order)
    if order.status == order.Status.CLAIMED:
        return order.claimed_by
    return None


def poster_is_stalling(order: IndustryLoyaltyPointMarketOrder) -> bool:
    """True when the order's own poster owes the next pre-LP step.

    Only then may a stalled order be auto-cancelled. When a claimer (the
    Conversion Team) is the one holding things up they are pestered daily
    instead, so a slow claimer never costs the poster their order.
    """
    if order.status not in PRE_LP_STATUSES:
        return False
    waiting = waiting_on(order)
    return waiting is not None and waiting.pk == order.created_by_id


def waiting_on_action(order: IndustryLoyaltyPointMarketOrder) -> str:
    """Short description of the pending action (e.g. for cancel reasons)."""
    if order.status == order.Status.AWAITING_LP:
        return f"send LP to **{_destination_label(order)}**"
    if order.status == order.Status.AWAITING_ISK:
        return (
            f"pay **{_isk_due(order):,} ISK** to "
            f"**{_isk_payout_label(order)}**"
        )
    return "confirm where the LP should go"


def stalled_cancel_reason(order: IndustryLoyaltyPointMarketOrder) -> str:
    return (
        "No progress for 48 hours while waiting on "
        f"**{_display_name(waiting_on(order))}** to "
        f"{waiting_on_action(order)}. Post a new order when you're ready."
    )


def _stalled_reminder_message(
    order: IndustryLoyaltyPointMarketOrder,
    *,
    waited_hours: int,
    cancel_at=None,
) -> str:
    mention = _user_mention(waiting_on(order))
    lines: list[str] = []
    if mention:
        lines.extend([mention, ""])
    lines.append(
        f":alarm_clock: Reminder — this order has been waiting on you to "
        f"{waiting_on_action(order)} for {waited_hours} hours."
    )
    if order.status == order.Status.AWAITING_LP:
        lines.append("Once it's sent, press **LP sent** below.")
    elif order.status == order.Status.AWAITING_ISK:
        lines.append("Once it's paid, press **ISK sent** below.")
    if cancel_at is not None:
        lines.append(
            "If nothing moves, this order is cancelled automatically "
            f"<t:{int(cancel_at.timestamp())}:R>."
        )
    lines.append(order_site_url(order))
    return "\n".join(lines)


def post_stalled_reminder(
    order: IndustryLoyaltyPointMarketOrder,
    *,
    waited_hours: int,
    cancel_at=None,
) -> bool:
    components = None
    if order.status == order.Status.AWAITING_LP:
        components = lp_sent_components(order.pk)
    elif order.status == order.Status.AWAITING_ISK:
        components = isk_sent_components(order.pk)
    return post_order_status_update(
        order,
        message=_stalled_reminder_message(
            order, waited_hours=waited_hours, cancel_at=cancel_at
        ),
        components=components,
    )


def post_stale_open_orders_digest(orders, *, now) -> bool:
    """Tell the Conversion Team about orders nobody has taken for a week."""
    channel_id = lp_conversion_alert_channel_id()
    if not channel_id or not orders:
        return False
    count = len(orders)
    lines = [
        f":hourglass: **{count} LP buyback "
        f"order{'s' if count != 1 else ''}** "
        f"open for a week or more with no taker:",
    ]
    for order in orders[:STALE_DIGEST_MAX_LINES]:
        days = int((now - order.status_changed_at).total_seconds() // 86400)
        thread = (
            f"<#{order.discord_thread_id}>"
            if order.discord_thread_id
            else order_site_url(order)
        )
        lines.append(
            f"- **{order_thread_title(order)}** by "
            f"{_display_name(order.created_by)} — {days}d, "
            f"{remaining_quantity(order):,} LP unclaimed · {thread}"
        )
    if count > STALE_DIGEST_MAX_LINES:
        lines.append(
            f"…and {count - STALE_DIGEST_MAX_LINES} more on the site."
        )
    try:
        discord.create_message(
            channel_id=channel_id, payload={"content": "\n".join(lines)}
        )
    except Exception as exc:
        logger.error("Failed posting stale LP order digest: %s", exc)
        return False
    return True
