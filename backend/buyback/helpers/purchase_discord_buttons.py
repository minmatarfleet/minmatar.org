"""Discord button payloads for hangar buyback purchase-order threads."""

COMPLETE_CUSTOM_ID_PREFIX = "buyback:complete:"
CANCEL_CUSTOM_ID_PREFIX = "buyback:cancel:"


def complete_custom_id(order_id: int) -> str:
    return f"{COMPLETE_CUSTOM_ID_PREFIX}{int(order_id)}"


def cancel_custom_id(order_id: int) -> str:
    return f"{CANCEL_CUSTOM_ID_PREFIX}{int(order_id)}"


def order_action_components(order_id: int) -> list[dict]:
    return [
        {
            "type": 1,
            "components": [
                {
                    "type": 2,
                    "style": 3,
                    "label": "Complete",
                    "custom_id": complete_custom_id(order_id),
                },
                {
                    "type": 2,
                    "style": 4,
                    "label": "Cancel",
                    "custom_id": cancel_custom_id(order_id),
                },
            ],
        }
    ]
