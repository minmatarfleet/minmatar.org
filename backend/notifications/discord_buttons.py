"""Discord notification DM helpers (button payloads, custom ids)."""

NOTIF_ACK_CUSTOM_ID_PREFIX = "notif_ack:"


def ack_custom_id(delivery_id: int) -> str:
    return f"{NOTIF_ACK_CUSTOM_ID_PREFIX}{int(delivery_id)}"


def mark_as_read_components(delivery_id: int) -> list[dict]:
    """Discord message components: one secondary button to ack/dismiss."""
    return [
        {
            "type": 1,  # ACTION_ROW
            "components": [
                {
                    "type": 2,  # BUTTON
                    "style": 2,  # Secondary
                    "label": "Mark as read",
                    "custom_id": ack_custom_id(delivery_id),
                }
            ],
        }
    ]


def link_button_components(label: str, url: str) -> list[dict]:
    """One link button. Replaces Mark as read when set on the payload."""
    return [
        {
            "type": 1,  # ACTION_ROW
            "components": [
                {
                    "type": 2,  # BUTTON
                    "style": 5,  # Link
                    "label": label,
                    "url": url,
                }
            ],
        }
    ]
