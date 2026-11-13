"""Discord forum-thread mirror for hangar buyback purchase orders."""

from __future__ import annotations

import logging

from django.conf import settings

from app.links import site_url
from buyback.helpers.purchase_discord_buttons import (
    close_components,
    contract_accepted_components,
    order_action_components,
)
from buyback.models import BuybackPurchaseOrder, EveBuybackSettings
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
    base = site_url()
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


def buyback_team_mentions() -> str:
    """Discord pings for coordinators who put sale contracts up."""
    users = (
        EveBuybackSettings.load()
        .coordinators.select_related("discord_user")
        .order_by("pk")
    )
    mentions = []
    for user in users:
        mention = _user_mention(user)
        if mention.startswith("<@"):
            mentions.append(mention)
    return " ".join(mentions)


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


def active_buyback_thread_ids() -> set[int] | None:
    """Unarchived thread ids in the sale forum (None if unknown)."""
    row = MIRROR.channel_row()
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
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Could not list active buyback sale threads: %s", exc)
        return None
    return {
        int(thread["id"])
        for thread in threads
        if str(thread.get("parent_id")) == str(channel_id)
    }


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


def _starter_pings(order: BuybackPurchaseOrder) -> str:
    team = [part for part in buyback_team_mentions().split() if part]
    buyer = _user_mention(order.created_by)
    parts = list(team) or ["Buyback team"]
    if buyer and buyer not in parts:
        parts.append(buyer)
    return " ".join(parts)


def order_starter_message(order: BuybackPurchaseOrder) -> str:
    header = [
        _starter_pings(order),
        "",
        f"**Purchase order #{order.pk}**",
        f"Pilot: {_display_name(order)}",
        f"Total: **{int(order.contract_total):,} ISK**",
        f"Status: {order.get_status_display()}",
        "",
        "Buyback team: put the contract up, then press **Contract up**.",
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
            discord_thread_id=thread_id,
            team_prompted=True,
        )
        order.discord_thread_id = thread_id
        order.team_prompted = True


def _coverage_note(order: BuybackPurchaseOrder) -> str:
    # Local import: purchase_orders imports this module at load time.
    # pylint: disable=import-outside-toplevel
    from buyback.helpers.purchase_orders import contract_coverage_note

    if not order.completed_by_id:
        return ""
    return contract_coverage_note(order)


def _message_with_note(lines: list[str], note: str) -> str:
    if not note:
        return "\n".join(lines)
    head, url = lines[:-1], lines[-1]
    message = "\n".join(head + [note, url])
    if len(message) <= 1900:
        return message
    room = 1900 - len("\n".join(head + [url])) - 2
    if room < 40:
        return "\n".join(lines)
    return "\n".join(head + [note[: room - 1] + "…", url])


def _completed_message(order: BuybackPurchaseOrder) -> str:
    if (
        order.settlement_step
        == BuybackPurchaseOrder.SettlementStep.AWAITING_ACCEPT
    ):
        headline = ":white_check_mark: Contract accepted — sale completed"
    elif (
        order.settlement_step
        == BuybackPurchaseOrder.SettlementStep.MANUAL_CLOSE
    ):
        headline = ":white_check_mark: Sale closed"
    elif order.completed_by_id:
        actor = _user_mention(order.completed_by) or (
            order.completed_by.username if order.completed_by else ""
        )
        who = f" by **{actor}**" if actor else ""
        headline = f":white_check_mark: Sale completed{who}"
    else:
        headline = ":white_check_mark: Sale completed (contract matched)"
    mention = _user_mention(order.created_by)
    lines: list[str] = []
    if mention:
        lines.extend([mention, ""])
    lines.extend(
        [
            headline,
            f"**{int(order.contract_total):,} ISK**",
            order_site_url(order),
        ]
    )
    return _message_with_note(lines, _coverage_note(order))


def _participant_mentions(order: BuybackPurchaseOrder) -> str:
    team = buyback_team_mentions().split()
    buyer = _user_mention(order.created_by)
    parts = list(team)
    if buyer and buyer not in parts:
        parts.append(buyer)
    return " ".join(parts)


def _cancelled_message(order: BuybackPurchaseOrder) -> str:
    mentions = _participant_mentions(order)
    lines: list[str] = []
    if mentions:
        lines.extend([mentions, ""])
    lines.append(":no_entry_sign: Sale cancelled")
    if order.cancel_reason:
        lines.append(order.cancel_reason)
    lines.append(order_site_url(order))
    return "\n".join(lines)


def stalled_cancel_reason(order: BuybackPurchaseOrder) -> str:
    return (
        "No progress for 48 hours while waiting on the buyback team "
        f"to put the contract up for **{_display_name(order)}**. "
        "Post a new order when you're ready."
    )


def post_stalled_reminder(
    order: BuybackPurchaseOrder,
    *,
    waited_hours: int,
    cancel_at=None,
) -> bool:
    """Ping whoever owes the next button. False when Discord did not get it."""
    step = order.settlement_step
    waiting_on_team = step == BuybackPurchaseOrder.SettlementStep.CONTRACT_UP
    if waiting_on_team:
        mention = _participant_mentions(order) or "Buyback team"
        waiting = "the buyback team to put the contract up"
        pressed = "Once it's up, press **Contract up** below."
        components = order_action_components(order.pk)
    else:
        mention = _user_mention(order.created_by)
        waiting = "you to accept the contract"
        pressed = "Once it's accepted, press **Contract accepted** below."
        components = contract_accepted_components(order.pk)
    lines: list[str] = []
    if mention:
        lines.extend([mention, ""])
    lines.append(
        ":alarm_clock: Reminder — this sale has been waiting on "
        f"{waiting} for {waited_hours} hours."
    )
    lines.append(pressed)
    if cancel_at is not None:
        lines.append(
            "If nothing moves, this order is cancelled automatically "
            f"<t:{int(cancel_at.timestamp())}:R>."
        )
    lines.append(order_site_url(order))
    return MIRROR.post(order.discord_thread_id, "\n".join(lines), components)


def notify_contract_up(order: BuybackPurchaseOrder) -> None:
    """Ping the buyer to accept the contract the team just put up."""
    if not order.discord_thread_id:
        return
    if (
        order.settlement_step
        != BuybackPurchaseOrder.SettlementStep.AWAITING_ACCEPT
    ):
        return
    mention = _user_mention(order.created_by)
    lines = []
    if mention:
        lines.extend([mention, ""])
    lines.extend(
        [
            "Contract is up. Accept it in game, then press "
            "**Contract accepted**.",
            order_site_url(order),
        ]
    )
    MIRROR.post(
        order.discord_thread_id,
        "\n".join(lines),
        contract_accepted_components(order.pk),
    )


def _legacy_close_message(order: BuybackPurchaseOrder) -> str:
    team = buyback_team_mentions() or "Buyback team"
    return "\n".join(
        [
            team,
            "",
            f"Sale #{order.pk} is still open.",
            "Press **Close** when it's done.",
            order_site_url(order),
        ]
    )


def prompt_team_for_open_sales() -> int:
    """Tag the buyback team once so they can close threads already open.

    New sales are prompted when their thread is created and stay on
    Contract up. This pass is only the sales that were already open.
    """
    step = BuybackPurchaseOrder.SettlementStep
    orders = (
        BuybackPurchaseOrder.objects.filter(
            status=BuybackPurchaseOrder.Status.PENDING,
            settlement_step=step.CONTRACT_UP,
            team_prompted=False,
            discord_thread_id__isnull=False,
        )
        .select_related("created_by", "created_by__discord_user")
        .order_by("pk")
    )
    posted = 0
    for order in orders:
        if not MIRROR.post(
            order.discord_thread_id,
            _legacy_close_message(order),
            close_components(order.pk),
        ):
            continue
        posted += BuybackPurchaseOrder.objects.filter(
            pk=order.pk,
            status=BuybackPurchaseOrder.Status.PENDING,
            settlement_step=step.CONTRACT_UP,
            team_prompted=False,
        ).update(
            team_prompted=True,
            settlement_step=step.MANUAL_CLOSE,
        )
    return posted


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
