"""Discord pieces of a tribe invite DM: its buttons and its answered edit.

The bot handles Decline; its prefix must match bot/app/custom_ids.py
(backend/discord/test_bot_custom_ids.py checks it).
"""

from notifications.discord_format import feature_color

DECLINE_CUSTOM_ID_PREFIX = "tribe_invite:decline:"

# Discord component types and button styles.
_ACTION_ROW = 1
_BUTTON = 2
_STYLE_SECONDARY = 2
_STYLE_LINK = 5


def decline_custom_id(invitation_id: int) -> str:
    return f"{DECLINE_CUSTOM_ID_PREFIX}{int(invitation_id)}"


def invite_components(invitation_id: int, url: str) -> list[dict]:
    """Open invite (a link to the group page) and Decline (bot button)."""
    buttons = []
    if url:
        buttons.append(
            {
                "type": _BUTTON,
                "style": _STYLE_LINK,
                "label": "Open invite",
                "url": url,
            }
        )
    buttons.append(
        {
            "type": _BUTTON,
            "style": _STYLE_SECONDARY,
            "label": "Decline",
            "custom_id": decline_custom_id(invitation_id),
        }
    )
    return [{"type": _ACTION_ROW, "components": buttons}]


def answered_embed(
    *, title: str, description: str, url: str = "", colored: bool = False
) -> dict:
    """The embed an answered invite DM is edited to (no buttons)."""
    embed = {
        "author": {"name": "Tribes"},
        "title": title,
        "description": description,
    }
    if colored:
        embed["color"] = feature_color("tribes")
    if url:
        embed["url"] = url
    return embed
