"""Discord notification DM helpers (button payloads, custom ids)."""

NOTIF_ACK_CUSTOM_ID_PREFIX = "notif_ack:"


def ack_custom_id(delivery_id: int) -> str:
    return f"{NOTIF_ACK_CUSTOM_ID_PREFIX}{int(delivery_id)}"


def parse_ack_custom_id(custom_id: str) -> int | None:
    if not custom_id or not custom_id.startswith(NOTIF_ACK_CUSTOM_ID_PREFIX):
        return None
    raw = custom_id[len(NOTIF_ACK_CUSTOM_ID_PREFIX) :]
    if not raw.isdigit():
        return None
    return int(raw)


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
