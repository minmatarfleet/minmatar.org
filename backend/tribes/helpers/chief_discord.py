"""Buttons on the executor's chief-volunteer DM.

The bot handles Appoint and Not now; the prefixes must match
bot/app/custom_ids.py (backend/discord/test_bot_custom_ids.py checks it).
"""

APPOINT_CUSTOM_ID_PREFIX = "tribe_chief:appoint:"
DECLINE_CUSTOM_ID_PREFIX = "tribe_chief:decline:"

# Discord component types and button styles.
_ACTION_ROW = 1
_BUTTON = 2
_STYLE_SECONDARY = 2
_STYLE_SUCCESS = 3
_STYLE_LINK = 5


def appoint_custom_id(volunteer_id: int) -> str:
    return f"{APPOINT_CUSTOM_ID_PREFIX}{int(volunteer_id)}"


def decline_custom_id(volunteer_id: int) -> str:
    return f"{DECLINE_CUSTOM_ID_PREFIX}{int(volunteer_id)}"


def volunteer_components(volunteer_id: int, url: str) -> list[dict]:
    """Appoint as chief, Not now (bot buttons) and All volunteers (link)."""
    buttons = [
        {
            "type": _BUTTON,
            "style": _STYLE_SUCCESS,
            "label": "Appoint as chief",
            "custom_id": appoint_custom_id(volunteer_id),
        },
        {
            "type": _BUTTON,
            "style": _STYLE_SECONDARY,
            "label": "Not now",
            "custom_id": decline_custom_id(volunteer_id),
        },
    ]
    if url:
        buttons.append(
            {
                "type": _BUTTON,
                "style": _STYLE_LINK,
                "label": "All volunteers",
                "url": url,
            }
        )
    return [{"type": _ACTION_ROW, "components": buttons}]
