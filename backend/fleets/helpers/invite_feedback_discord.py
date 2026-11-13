"""The Answer button on the fleet invite feedback DM.

The bot handles the click and opens the form as a Discord pop-up (bot/app/
fleet_invites/feedback_form.py). The prefix must match bot/app/custom_ids.py
(backend/discord/test_bot_custom_ids.py checks it). This module imports
nothing from the app so the notification type can use it.
"""

ANSWER_CUSTOM_ID_PREFIX = "invite_feedback:answer:"


def answer_custom_id(round_id: int) -> str:
    return f"{ANSWER_CUSTOM_ID_PREFIX}{int(round_id)}"


def answer_button(round_id: int) -> dict:
    return {
        "type": 2,  # BUTTON
        "style": 1,  # Primary
        "label": "Answer",
        "custom_id": answer_custom_id(round_id),
    }


def website_button(url: str) -> dict:
    return {
        "type": 2,  # BUTTON
        "style": 5,  # Link
        "label": "Answer on the website",
        "url": url,
    }
