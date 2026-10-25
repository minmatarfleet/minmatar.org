"""
Discord button custom_id contract.

The backend posts most of these buttons over the REST API and the bot handles
the clicks, so both sides must agree on every id. Posted messages keep their
custom_ids forever: never change or remove a prefix here, only add new ones.

This module must not import discord (or anything outside the standard
library). The backend's tests load it by file path and check the backend's
own ids against it: backend/discord/test_bot_custom_ids.py.
"""

# Hangar buyback purchase orders (backend: buyback/helpers/purchase_discord_buttons.py)
BUYBACK_COMPLETE_PREFIX = "buyback:complete:"
BUYBACK_CANCEL_PREFIX = "buyback:cancel:"

# LP buyback settlement acks (backend: industry/helpers/lp_buyback_discord_buttons.py)
LP_BUYBACK_LP_SENT_PREFIX = "lp_buyback:lp:"
LP_BUYBACK_ISK_SENT_PREFIX = "lp_buyback:isk:"

# Notification "Mark as read" (backend: notifications/discord_buttons.py)
NOTIF_ACK_PREFIX = "notif_ack:"

# NPSI event DMs (backend: fleets/helpers/npsi_discord.py)
NPSI_POST_PREFIX = "npsi:create:"
# Older DMs used "npsi:post:"; still handled for messages already sent.
NPSI_POST_ALIAS_PREFIX = "npsi:post:"
NPSI_PREPING_PREFIX = "npsi:preping:"
NPSI_TRACK_PREFIX = "npsi:track:"

# Tribe group invite DMs (backend: tribes/helpers/invitation_discord.py)
TRIBE_INVITE_DECLINE_PREFIX = "tribe_invite:decline:"

# Fleet invite DMs (backend: fleets/helpers/private_fleet_discord.py)
FLEET_INVITE_OUT_PREFIX = "fleet_invite:out:"
FLEET_INVITE_STOP_PREFIX = "fleet_invite:stop:"

# Help tickets (bot-only: the bot posts these itself)
HELP_TICKET_CLOSE_PREFIX = "help_ticket_close:"
HELP_TICKET_CLOSE_REASON_PREFIX = "help_ticket_close_reason:"
HELP_TICKET_SELECT_CUSTOM_ID = "help_ticket_select"


def custom_id(prefix: str, object_id: int) -> str:
    """The custom_id for one object, e.g. custom_id(BUYBACK_COMPLETE_PREFIX, 7)."""
    return f"{prefix}{int(object_id)}"


def template(prefix: str, group: str) -> str:
    """discord.py DynamicItem template matching custom_id(prefix, n)."""
    return f"{prefix}(?P<{group}>[0-9]+)"


BUYBACK_COMPLETE_TEMPLATE = template(BUYBACK_COMPLETE_PREFIX, "order_id")
BUYBACK_CANCEL_TEMPLATE = template(BUYBACK_CANCEL_PREFIX, "order_id")
LP_BUYBACK_LP_SENT_TEMPLATE = template(LP_BUYBACK_LP_SENT_PREFIX, "order_id")
LP_BUYBACK_ISK_SENT_TEMPLATE = template(LP_BUYBACK_ISK_SENT_PREFIX, "order_id")
NOTIF_ACK_TEMPLATE = template(NOTIF_ACK_PREFIX, "delivery_id")
NPSI_POST_TEMPLATE = template(NPSI_POST_PREFIX, "event_id")
NPSI_POST_ALIAS_TEMPLATE = template(NPSI_POST_ALIAS_PREFIX, "event_id")
NPSI_PREPING_TEMPLATE = template(NPSI_PREPING_PREFIX, "event_id")
NPSI_TRACK_TEMPLATE = template(NPSI_TRACK_PREFIX, "event_id")
TRIBE_INVITE_DECLINE_TEMPLATE = template(
    TRIBE_INVITE_DECLINE_PREFIX, "invitation_id"
)
FLEET_INVITE_OUT_TEMPLATE = template(FLEET_INVITE_OUT_PREFIX, "invite_id")
FLEET_INVITE_STOP_TEMPLATE = template(FLEET_INVITE_STOP_PREFIX, "invite_id")
HELP_TICKET_CLOSE_TEMPLATE = template(HELP_TICKET_CLOSE_PREFIX, "ticket_id")
HELP_TICKET_CLOSE_REASON_TEMPLATE = template(
    HELP_TICKET_CLOSE_REASON_PREFIX, "ticket_id"
)
